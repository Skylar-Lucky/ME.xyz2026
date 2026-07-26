import type {GraphNode,GraphLink} from "../types/memoryGraph";
import {stableHash} from "./stableHash";

export const BRAIN_CENTER={x:0,y:0};
export const BRAIN_SELF_POSITION={x:-600,y:600};
export const BRANCH_ANGLES_DEG=[-72,-50,-28,-6] as const;

export function applyInitialLayout(nodes:GraphNode[]){
 const events=nodes.filter(node=>node.type==="event").sort((a,b)=>a.id.localeCompare(b.id));
 const emotions=nodes.filter(node=>node.type==="emotion").sort((a,b)=>a.id.localeCompare(b.id));
 const branches=nodes.filter(node=>node.type==="branch_anchor").sort((a,b)=>a.id.localeCompare(b.id));
 const eventOrder=new Map(events.map((node,index)=>[node.id,index]));
 const emotionOrder=new Map(emotions.map((node,index)=>[node.id,index]));
 const branchOrder=new Map(branches.map((node,index)=>[node.id,index]));
 const goldenAngle=Math.PI*(3-Math.sqrt(5));
 const positioned=nodes.map(original=>{
   const node={...original};
   if(node.type==="self"){
     node.x=BRAIN_SELF_POSITION.x;node.y=BRAIN_SELF_POSITION.y;
     node.fx=BRAIN_SELF_POSITION.x;node.fy=BRAIN_SELF_POSITION.y;
   }else if(node.type==="event"){
     const index=eventOrder.get(node.id)??0;
     const radial=Math.sqrt((index+.7)/Math.max(1,events.length));
     const angle=index*goldenAngle-.35;
     node.x=Math.cos(angle)*500*radial;
     node.y=Math.sin(angle)*340*radial-20;
   }else if(node.type==="emotion"){
     const index=emotionOrder.get(node.id)??0;
     const angle=index*(Math.PI*2/Math.max(1,emotions.length))-.45;
     node.x=Math.cos(angle)*540;
     node.y=Math.sin(angle)*360-18;
   }else if(node.type==="branch_anchor"){
     const index=branchOrder.get(node.id)??0;
     const angle=(BRANCH_ANGLES_DEG[index%BRANCH_ANGLES_DEG.length])*Math.PI/180;
     const radius=290+index*32;
     node.x=BRAIN_SELF_POSITION.x+Math.cos(angle)*radius;
     node.y=BRAIN_SELF_POSITION.y+Math.sin(angle)*radius;
   }
   return node;
 });
 const byId=new Map(positioned.map(node=>[node.id,node]));
 positioned.forEach(node=>{
   if(node.type==="viewpoint"){
     const event=byId.get(node.id.replace("viewpoint:",""));
     if(event){
       const side=(stableHash(node.id)&1)?1:-1;
       node.x=(event.x??0)+side*70;node.y=(event.y??0)+50;
     }
   }
 });
 return positioned;
}

export function neighbors(id:string,links:GraphLink[]){
 const result=new Set([id]);
 links.forEach(link=>{
   const source=typeof link.source==="string"?link.source:link.source.id;
   const target=typeof link.target==="string"?link.target:link.target.id;
   if(source===id)result.add(target);
   if(target===id)result.add(source);
 });
 return result;
}

export function isGraphNode(value:unknown):value is GraphNode{
 return typeof value==="object"&&value!==null&&"id" in value&&"type" in value;
}
