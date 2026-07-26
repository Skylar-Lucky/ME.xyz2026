import {describe,expect,it} from "vitest";
import {buildFocusHighlight,buildTimelineDimming} from "./graphView";
import type {GraphLink,GraphNode} from "../types/memoryGraph";

const nodes:GraphNode[]=[
  {id:"self",type:"self",label:"我",depth:0},
  {id:"branch:main",type:"branch_anchor",label:"主线",depth:1,branchId:"main"},
  {id:"e1",type:"event",label:"一",depth:1,branchId:"main",eventTime:"2026-01-01"},
  {id:"e2",type:"event",label:"二",depth:2,branchId:"main",eventTime:"2026-02-01"},
  {id:"emotion:hope",type:"emotion",label:"期待",depth:3},
  {id:"viewpoint:e1",type:"viewpoint",label:"观点",depth:1,branchId:"main"},
];
const links:GraphLink[]=[
  {id:"branch",source:"self",target:"branch:main",type:"BRANCH_FROM",weight:1},
  {id:"start",source:"branch:main",target:"e1",type:"BRANCH_START",weight:1},
  {id:"next",source:"e1",target:"e2",type:"NEXT_EVENT",weight:1},
  {id:"emotion",source:"e1",target:"emotion:hope",type:"HAS_EMOTION",weight:.8},
  {id:"view",source:"e1",target:"viewpoint:e1",type:"HAS_VIEWPOINT",weight:.35},
];

describe("graph view",()=>{
  it("highlights branch event links without semantic links for event focus",()=>{
    const result=buildFocusHighlight(nodes,links,"e1");
    expect(result.linkIds).toEqual(new Set(["branch","start","next"]));
    expect(result.linkIds.has("emotion")).toBe(false);
    expect(result.linkIds.has("view")).toBe(false);
  });
  it("emotion focus only highlights direct emotion links",()=>{
    expect(buildFocusHighlight(nodes,links,"emotion:hope").linkIds).toEqual(new Set(["emotion"]));
  });
  it("identity focus includes branch events, viewpoints and emotions",()=>{
    const result=buildFocusHighlight(nodes,links,"branch:main");
    expect(result.nodeIds).toEqual(new Set(["branch:main","self","e1","e2","emotion:hope","viewpoint:e1"]));
    expect(result.linkIds).toEqual(new Set(["branch","start","next","emotion","view"]));
  });
  it("timeline keeps all nodes and dims future dependencies",()=>{
    const early=buildTimelineDimming(nodes,links,new Date("2026-01-15").getTime());
    expect(early.visibleEventCount).toBe(1);
    expect(early.dimNodeIds.has("e1")).toBe(false);
    expect(early.dimNodeIds.has("e2")).toBe(true);
    expect(early.dimNodeIds.has("emotion:hope")).toBe(false);
    expect(early.dimLinkIds.has("next")).toBe(true);
  });
});
