import {expect,test} from "vitest";
import {EventDecoder} from "../src/stream";
test("event limits apply independently inside a combined network chunk",()=>{
 const d=new EventDecoder();
 const event='data: '+JSON.stringify({type:"token",text:"x".repeat(70000)})+'\n\n';
 expect(d.push(event+event)).toHaveLength(2);
});
test("known event names still require valid payloads",()=>{
 for(const value of [{type:"token",text:1},{type:"result",response:{}},{type:"error",error:{message:1}}])
  expect(()=>new EventDecoder().push('data: '+JSON.stringify(value)+'\n\n')).toThrow();
});
