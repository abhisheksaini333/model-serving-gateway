import {expect,test,vi} from "vitest";
import {request} from "../src/api";
test("credentials are limited to local API requests",async()=>{
 const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
 try {
  for(const path of ["https://evil/ops/requests","//evil/ops/requests","/ops/../outside"])
   await expect(request("secret",path)).rejects.toThrow(/destination/);
  expect(fetch).not.toHaveBeenCalled();
 }finally{vi.unstubAllGlobals();}
});
test("redirects are refused and unreadable errors retain status",async()=>{
 const fetch=vi.fn().mockResolvedValue({ok:false,status:502,json:async()=>{throw new SyntaxError("gateway");}});vi.stubGlobal("fetch",fetch);
 try{
  await expect(request("secret","/ops/summary")).rejects.toThrow(/502/);
  expect(fetch.mock.calls[0][1].redirect).toBe("error");
 }finally{vi.unstubAllGlobals();}
});
