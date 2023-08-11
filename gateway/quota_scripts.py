"""Atomic quota reservations use Redis time and tenant-local hash slots."""
RESERVE = """
local now = tonumber(redis.call('TIME')[1])
local window = math.floor(now / tonumber(ARGV[6]))
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
if tonumber(redis.call('HGET', KEYS[1], 'window') or '-1') ~= window then
    redis.call('HSET', KEYS[1], 'window', window, 'requests', 0, 'tokens', 0)
end
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[4]) then return {'tenant_concurrency'} end
if tonumber(redis.call('HGET', KEYS[1], 'requests')) >= tonumber(ARGV[3]) then return {'request_quota'} end
if tonumber(redis.call('HGET', KEYS[1], 'tokens')) + tonumber(ARGV[2]) > tonumber(ARGV[5]) then return {'token_quota'} end
if redis.call('ZSCORE', KEYS[2], ARGV[1]) then return {'duplicate_reservation'} end
redis.call('HINCRBY', KEYS[1], 'requests', 1)
redis.call('HINCRBY', KEYS[1], 'tokens', ARGV[2])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[6]) * 2)
redis.call('ZADD', KEYS[2], now + tonumber(ARGV[7]), ARGV[1])
redis.call('EXPIRE', KEYS[2], math.max(tonumber(ARGV[7]) + 60, 180))
return {'ok', tostring(window)}
"""

SETTLE = """
local removed = redis.call('ZREM', KEYS[2], ARGV[1])
if removed == 1 and tonumber(ARGV[3]) > 0 and redis.call('HGET', KEYS[1], 'window') == ARGV[2] then
    redis.call('HINCRBY', KEYS[1], 'tokens', -tonumber(ARGV[3]))
end
return removed
"""
