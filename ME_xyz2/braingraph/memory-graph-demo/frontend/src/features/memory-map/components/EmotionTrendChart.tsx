import {useMemo} from "react";
import type {GraphNode} from "../types/memoryGraph";
import styles from "../styles/memoryMap.module.css";

export const EMOTION_SCORES:Record<string,number>={
  anger:0,sadness:.12,anxiety:.25,confusion:.42,surprise:.5,calm:.6,
  satisfaction:.78,optimism:.9,joy:1,
};

export function eventEmotionScore(node:GraphNode){
  if(!node.emotions?.length)return .5;
  const total=node.emotions.reduce((sum,item)=>sum+(item.score??EMOTION_SCORES[item.code]??.5)*item.intensity,0);
  const weight=node.emotions.reduce((sum,item)=>sum+item.intensity,0);
  return weight?total/weight:.5;
}

function smoothPath(points:{x:number;y:number}[]){
  if(!points.length)return"";
  if(points.length===1)return`M ${points[0].x} ${points[0].y}`;
  return points.reduce((path,point,index)=>{
    if(index===0)return`M ${point.x} ${point.y}`;
    const previous=points[index-1];
    const mid=(previous.x+point.x)/2;
    return`${path} C ${mid} ${previous.y}, ${mid} ${point.y}, ${point.x} ${point.y}`;
  },"");
}

export function EmotionTrendChart({events,currentTime}:{events:GraphNode[];currentTime:number}){
  const series=useMemo(()=>events.filter(node=>node.eventTime).map(node=>({
    time:new Date(node.eventTime!).getTime(),score:eventEmotionScore(node),
  })).sort((a,b)=>a.time-b.time),[events]);
  const width=360,height=150,pad={left:34,right:12,top:12,bottom:25};
  const min=series[0]?.time??0,max=series.at(-1)?.time??1,span=Math.max(1,max-min);
  const points=series.map(item=>({x:pad.left+(item.time-min)/span*(width-pad.left-pad.right),y:pad.top+(1-item.score)*(height-pad.top-pad.bottom)}));
  const cursorX=pad.left+Math.max(0,Math.min(1,(currentTime-min)/span))*(width-pad.left-pad.right);
  return <section className={styles.trendCard}><div className={styles.analyticsTitle}><b>情绪趋势</b><span>消极 0 — 1 积极</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="按时间变化的情绪分数">
      {[0,.5,1].map(value=><g key={value}><line x1={pad.left} x2={width-pad.right} y1={pad.top+(1-value)*(height-pad.top-pad.bottom)} y2={pad.top+(1-value)*(height-pad.top-pad.bottom)} className={styles.chartGrid}/><text x={4} y={pad.top+(1-value)*(height-pad.top-pad.bottom)+4} className={styles.chartLabel}>{value.toFixed(1)}</text></g>)}
      <path d={smoothPath(points)} className={styles.chartLine}/>
      {points.map((point,index)=><circle key={index} cx={point.x} cy={point.y} r="2.6" className={styles.chartPoint}/>)}
      <line x1={cursorX} x2={cursorX} y1={pad.top} y2={height-pad.bottom} className={styles.chartCursor}/>
      <text x={pad.left} y={height-5} className={styles.chartLabel}>{series[0]?new Date(series[0].time).toLocaleDateString("zh-CN",{month:"short",day:"numeric"}):"-"}</text>
      <text x={width-pad.right} textAnchor="end" y={height-5} className={styles.chartLabel}>{series.at(-1)?new Date(series.at(-1)!.time).toLocaleDateString("zh-CN",{month:"short",day:"numeric"}):"-"}</text>
    </svg></section>;
}
