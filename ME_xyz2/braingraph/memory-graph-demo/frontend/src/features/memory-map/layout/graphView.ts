import type {GraphLink,GraphNode} from "../types/memoryGraph";

export const endpointId=(endpoint:string|GraphNode)=>typeof endpoint==="string"?endpoint:endpoint.id;

export function buildFocusHighlight(nodes:GraphNode[],links:GraphLink[],focusId?:string){
  const nodeIds=new Set<string>();
  const linkIds=new Set<string>();
  if(!focusId)return{nodeIds,linkIds};
  nodeIds.add(focusId);
  const focus=nodes.find(node=>node.id===focusId);
  const incident=links.filter(link=>endpointId(link.source)===focusId||endpointId(link.target)===focusId);
  incident.forEach(link=>{
    nodeIds.add(endpointId(link.source));
    nodeIds.add(endpointId(link.target));
  });
  if(focus?.type==="emotion"){
    incident.filter(link=>link.type==="HAS_EMOTION").forEach(link=>linkIds.add(link.id));
    return{nodeIds,linkIds};
  }
  if(focus?.type==="branch_anchor"){
    const branchEvents=new Set(nodes.filter(node=>node.type==="event"&&node.branchId===focus.branchId).map(node=>node.id));
    branchEvents.forEach(id=>nodeIds.add(id));
    links.forEach(link=>{
      const source=endpointId(link.source),target=endpointId(link.target);
      const structural=["NEXT_EVENT","BRANCH_START","BRANCH_FROM","SELF_START"].includes(link.type)
        &&(branchEvents.has(source)||branchEvents.has(target)||source===focusId||target===focusId);
      const viewpoint=link.type==="HAS_VIEWPOINT"&&branchEvents.has(source);
      const emotion=link.type==="HAS_EMOTION"&&branchEvents.has(source);
      if(structural||viewpoint||emotion){
        linkIds.add(link.id);
        nodeIds.add(source);
        nodeIds.add(target);
      }
    });
    return{nodeIds,linkIds};
  }
  let event=focus?.type==="event"?focus:undefined;
  if(focus?.type==="viewpoint"){
    const relation=incident.find(link=>link.type==="HAS_VIEWPOINT");
    const eventId=relation&&(endpointId(relation.source)===focusId?endpointId(relation.target):endpointId(relation.source));
    event=nodes.find(node=>node.id===eventId&&node.type==="event");
    if(event)nodeIds.add(event.id);
  }
  if(event){
    const branchId=event.branchId;
    const branchEvents=new Set(nodes.filter(node=>node.type==="event"&&node.branchId===branchId).map(node=>node.id));
    nodes.filter(node=>node.branchId===branchId&&["event","branch_anchor","viewpoint"].includes(node.type))
      .forEach(node=>nodeIds.add(node.id));
    links.forEach(link=>{
      const source=endpointId(link.source),target=endpointId(link.target);
      const structural=["NEXT_EVENT","BRANCH_START","BRANCH_FROM","SELF_START"].includes(link.type)
        &&(branchEvents.has(source)||branchEvents.has(target)||source===`branch:${branchId}`||target===`branch:${branchId}`);
      const viewpoint=link.type==="HAS_VIEWPOINT"&&branchEvents.has(source);
      const emotion=link.type==="HAS_EMOTION"&&branchEvents.has(source);
      if(structural)linkIds.add(link.id);
      if(structural||viewpoint||emotion){nodeIds.add(source);nodeIds.add(target)}
    });
  }
  return{nodeIds,linkIds};
}

export function buildTimelineDimming(nodes:GraphNode[],links:GraphLink[],endTime:number){
  const visibleEvents=new Set(nodes.filter(node=>node.type==="event"&&node.eventTime&&new Date(node.eventTime).getTime()<=endTime).map(node=>node.id));
  const dimNodeIds=new Set(nodes.filter(node=>node.type==="event"&&!visibleEvents.has(node.id)).map(node=>node.id));
  nodes.forEach(node=>{
    if(node.type==="viewpoint"&&dimNodeIds.has(node.id.replace("viewpoint:","")))dimNodeIds.add(node.id);
    if(node.type==="branch_anchor"){
      const branchEvents=nodes.filter(event=>event.type==="event"&&event.branchId===node.branchId);
      if(branchEvents.length&&branchEvents.every(event=>dimNodeIds.has(event.id)))dimNodeIds.add(node.id);
    }
  });
  nodes.filter(node=>node.type==="emotion").forEach(emotion=>{
    const connectedEvents=links.filter(link=>link.type==="HAS_EMOTION"&&endpointId(link.target)===emotion.id).map(link=>endpointId(link.source));
    if(connectedEvents.length&&connectedEvents.every(eventId=>dimNodeIds.has(eventId)))dimNodeIds.add(emotion.id);
  });
  const dimLinkIds=new Set(links.filter(link=>dimNodeIds.has(endpointId(link.source))||dimNodeIds.has(endpointId(link.target))).map(link=>link.id));
  return{dimNodeIds,dimLinkIds,visibleEventCount:visibleEvents.size};
}
