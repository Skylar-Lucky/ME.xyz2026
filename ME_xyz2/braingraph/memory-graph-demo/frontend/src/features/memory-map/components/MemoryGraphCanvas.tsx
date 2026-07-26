import {useCallback,useEffect,useMemo,useRef,useState} from "react";
import {forceCollide} from "d3-force";
import ForceGraph2D, {type ForceGraphMethods} from "react-force-graph-2d";
import {applyInitialLayout,neighbors} from "../layout/graphLayout";
import {buildFocusHighlight,endpointId} from "../layout/graphView";
import type {GraphLink,GraphNode} from "../types/memoryGraph";
import styles from "../styles/memoryMap.module.css";

// 图谱节点配色：起点我=粉，事件=天蓝，情绪=黄，观点=绿，角色事件(分支锚点)=紫
const color=(node:GraphNode)=>node.type==="self"?"#FF5FC8":
  node.type==="event"?"#4DCAFF":
  node.type==="emotion"?"#FFE66E":
  node.type==="viewpoint"?"#58F287":"#C77EFF";

function drawBrainGradient(ctx:CanvasRenderingContext2D){
 ctx.save();
 const ambient=ctx.createRadialGradient(0,-10,30,0,-10,720);
 ambient.addColorStop(0,"rgba(0,0,0,.42)");
 ambient.addColorStop(.62,"rgba(0,0,0,.12)");
 ambient.addColorStop(1,"rgba(0,0,0,0)");
 ctx.fillStyle=ambient;
 ctx.fillRect(-1000,-800,2000,1600);
 const brain=ctx.createRadialGradient(20,-35,35,20,-35,480);
 brain.addColorStop(0,"#020203");
 brain.addColorStop(.5,"#07080a");
 brain.addColorStop(.82,"#0d0e12");
 brain.addColorStop(1,"#14151a");
 ctx.fillStyle=brain;
 ctx.shadowColor="rgba(0,0,0,.75)";
 ctx.shadowBlur=34;
 ctx.beginPath();
 ctx.moveTo(-600,600);
 ctx.lineTo(-250,180);
 ctx.bezierCurveTo(-405,115,-420,-95,-300,-210);
 ctx.bezierCurveTo(-205,-335,35,-365,215,-275);
 ctx.bezierCurveTo(390,-215,455,-70,405,80);
 ctx.bezierCurveTo(370,225,150,285,-60,270);
 ctx.bezierCurveTo(-150,270,-205,235,-250,180);
 ctx.closePath();
 ctx.fill();
 ctx.restore();
}

export function MemoryGraphCanvas({nodes,links,selectedId,focusId,dimNodeIds=new Set(),dimLinkIds=new Set(),onSelect,showEmotionLinks,showEventLinks,onReady}:{nodes:GraphNode[];links:GraphLink[];selectedId?:string;focusId?:string;dimNodeIds?:Set<string>;dimLinkIds?:Set<string>;onSelect:(n?:GraphNode)=>void;showEmotionLinks:boolean;showEventLinks:boolean;onReady?:(fit:()=>void)=>void}){
 const ref=useRef<ForceGraphMethods<GraphNode,GraphLink>|undefined>(undefined);
 const containerRef=useRef<HTMLDivElement>(null);
 const [size,setSize]=useState({width:800,height:600});
 const [hovered,setHovered]=useState<{node:GraphNode;left:number;top:number}>();
 const graph=useMemo(()=>({nodes:applyInitialLayout(nodes),links:links.map(l=>({...l}))}),[nodes,links]);
 const active=useMemo(()=>selectedId?neighbors(selectedId,links):null,[selectedId,links]);
 const focusHighlight=useMemo(()=>buildFocusHighlight(nodes,links,focusId),[nodes,links,focusId]);
 // 关联数（度数）：节点在 links 里被引用的次数，越多说明这个节点承载的连接越重要
 const degree=useMemo(()=>{
   const map=new Map<string,number>();
   links.forEach(link=>{
     const source=endpointId(link.source),target=endpointId(link.target);
     map.set(source,(map.get(source)??0)+1);
     map.set(target,(map.get(target)??0)+1);
   });
   return map;
 },[links]);
 // 节点半径 = 类型基准半径 + 关联数加成（开方缩放，避免个别高连接节点失控变大）
 const baseRadiusFor=useCallback((node:GraphNode)=>{
   const base=node.type==="self"?42:node.type==="event"?13:node.type==="branch_anchor"?21:node.type==="emotion"?9:6;
   if(node.type==="self")return base;
   const boost=Math.sqrt(degree.get(node.id)??0)*1.6;
   return base+Math.min(boost,base*0.9);
 },[degree]);
 useEffect(()=>{
   const element=containerRef.current;
   if(!element)return;
   const observer=new ResizeObserver(([entry])=>{
     const width=Math.max(1,Math.floor(entry.contentRect.width));
     const height=Math.max(1,Math.floor(entry.contentRect.height));
     setSize(current=>current.width===width&&current.height===height?current:{width,height});
   });
   observer.observe(element);
   return()=>observer.disconnect();
 },[]);
 useEffect(()=>{
   const instance=ref.current;
   if(!instance)return;
   const linkForce=instance.d3Force("link") as {distance:(value:(link:GraphLink)=>number)=>void;strength:(value:(link:GraphLink)=>number)=>void}|undefined;
   linkForce?.distance(link=>link.type==="HAS_EMOTION"?340:link.type==="HAS_VIEWPOINT"?112:link.type==="NEXT_EVENT"?190:225);
   linkForce?.strength(link=>link.type==="HAS_EMOTION"?.02:link.type==="HAS_VIEWPOINT"?.1:.15);
   const chargeForce=instance.d3Force("charge") as {strength:(value:number)=>void;distanceMax:(value:number)=>void}|undefined;
   chargeForce?.strength(-560);
   chargeForce?.distanceMax(1400);
   // 碰撞防重叠：半径按节点实际渲染大小 + 间距留白，中心密集区不再挤成一团
   instance.d3Force("collide",forceCollide<GraphNode>(node=>baseRadiusFor(node)+10).iterations(2));
   instance.d3ReheatSimulation();
 },[graph,baseRadiusFor]);
 useEffect(()=>{
   if(!focusId)return;
   const target=graph.nodes.find(node=>node.id===focusId);
   if(!target)return;
   const timer=window.setTimeout(()=>{
     ref.current?.centerAt(target.x??0,target.y??0,650);
   },180);
   return()=>window.clearTimeout(timer);
 },[focusId,graph]);
 const draw=useCallback((node:GraphNode,ctx:CanvasRenderingContext2D)=>{
   const baseRadius=baseRadiusFor(node);
   const nodeDegree=degree.get(node.id)??0;
   const radius=focusId===node.id?baseRadius*2.15:baseRadius;
   const focusOpacity=focusId?(node.id===focusId?1:focusHighlight.nodeIds.has(node.id)?0.48:0.08):(active&&!active.has(node.id)?0.18:1);
   const opacity=dimNodeIds.has(node.id)?Math.min(focusOpacity,.1):focusOpacity;ctx.save();ctx.globalAlpha=opacity;
   // 发光强度随关联数适度增强，让"承载更多连接"的节点在视觉上更突出
   ctx.shadowBlur=node.type==="self"?30:focusId===node.id?24:Math.min(22,8+nodeDegree*1.4);ctx.shadowColor=color(node);
   ctx.beginPath();if(node.type==="emotion"){const x=node.x??0,y=node.y??0;ctx.moveTo(x,y-radius);ctx.lineTo(x+radius,y);ctx.lineTo(x,y+radius);ctx.lineTo(x-radius,y);ctx.closePath()}else if(node.type==="viewpoint"){ctx.roundRect((node.x??0)-10,(node.y??0)-7,20,14,4)}else ctx.arc(node.x??0,node.y??0,radius,0,Math.PI*2);
   ctx.fillStyle=color(node);ctx.fill();ctx.lineWidth=selectedId===node.id?3:1.2;ctx.strokeStyle="#fff";ctx.stroke();
   ctx.restore()
 },[active,baseRadiusFor,degree,dimNodeIds,focusHighlight.nodeIds,focusId,selectedId]);
 const pointer=useCallback((n:GraphNode)=>baseRadiusFor(n)+4,[baseRadiusFor]);
 const handleHover=useCallback((node:GraphNode|null)=>{
   if(!node||node.type!=="event"){setHovered(undefined);return}
   const point=ref.current?.graph2ScreenCoords(node.x??0,node.y??0);
   if(point)setHovered({node,left:point.x+18,top:point.y+12});
 },[]);
 const eventLinkTypes=new Set(["NEXT_EVENT","BRANCH_START","BRANCH_FROM","SELF_START"]);
 return <div ref={containerRef} className="memoryGraphViewport"><ForceGraph2D ref={ref} width={size.width} height={size.height} graphData={graph} backgroundColor="#000000" nodeCanvasObject={draw} nodePointerAreaPaint={(n,c,ctx)=>{ctx.fillStyle=c;ctx.beginPath();ctx.arc(n.x??0,n.y??0,pointer(n),0,2*Math.PI);ctx.fill()}}
   onRenderFramePre={drawBrainGradient}
   linkColor={l=>{if(dimLinkIds.has(l.id))return"rgba(255,255,255,.035)";if(focusId&&!focusHighlight.linkIds.has(l.id))return"rgba(255,255,255,.045)";return l.type==="HAS_EMOTION"?"rgba(255,230,110,.72)":l.type==="HAS_VIEWPOINT"?"rgba(88,242,135,.62)":"rgba(199,126,255,.78)"}} linkWidth={l=>focusId&&focusHighlight.linkIds.has(l.id)?2.6:active&&active.has(endpointId(l.source))&&active.has(endpointId(l.target))?2.8:l.type==="HAS_EMOTION"?1.35:l.type==="SELF_START"?2:1}
   linkLineDash={l=>l.type==="HAS_EMOTION"?[4,5]:l.type==="HAS_VIEWPOINT"?[2,7]:null}
   linkVisibility={l=>(showEmotionLinks||l.type!=="HAS_EMOTION")&&(showEventLinks||!eventLinkTypes.has(l.type))}
   linkDirectionalArrowLength={l=>["NEXT_EVENT","BRANCH_FROM"].includes(l.type)?3:0}
   onNodeHover={handleHover} onNodeClick={n=>onSelect(n)} onBackgroundClick={()=>onSelect()} cooldownTicks={90} d3AlphaDecay={.045}
   onEngineStop={()=>{const fit=()=>{ref.current?.zoomToFit(450,54);window.setTimeout(()=>ref.current?.centerAt(0,0,300),480)};onReady?.(fit);fit()}}/>
   {hovered&&<div className={styles.eventTooltip} style={{left:hovered.left,top:hovered.top}}>
     <time>{hovered.node.eventTime?new Date(hovered.node.eventTime).toLocaleDateString("zh-CN"):"日期未记录"}</time>
     <strong>{hovered.node.content}</strong>
     <span>{hovered.node.personaName??hovered.node.branchId}</span>
   </div>}
 </div>;
}
