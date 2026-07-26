export type NodeType="self"|"event"|"branch_anchor"|"emotion"|"viewpoint";
export type LinkType="SELF_START"|"NEXT_EVENT"|"BRANCH_FROM"|"BRANCH_START"|"HAS_EMOTION"|"HAS_VIEWPOINT";
export interface GraphEmotion {code:string;label:string;intensity:number;score:number}
export interface GraphNode {id:string;type:NodeType;label:string;depth:number;content?:string;eventTime?:string;viewpoint?:string;branchId?:string;parentEventId?:string;conversationId?:string;sourceTurnId?:string;personaName?:string;emotions?:GraphEmotion[];count?:number;x?:number;y?:number;fx?:number;fy?:number}
export interface GraphLink {id:string;source:string|GraphNode;target:string|GraphNode;type:LinkType;weight:number}
export interface GraphResponse {version:number;nodes:GraphNode[];links:GraphLink[];stats:{eventCount:number;branchCount:number;emotionCount:number;viewpointCount:number}}
export interface EventDetail {event_id:string;event_time:string;event_content:string;emotions:{code:string;label:string;intensity:number}[];viewpoint:string;branch_id:string;parent_event_id?:string;conversation_id:string;source_turn_id:string;persona_name?:string;growth_summary:string;children:string[]}
export interface MemoryGraphApiConfig {baseUrl:string;getAuthHeaders?:()=>Record<string,string>|Promise<Record<string,string>>}
