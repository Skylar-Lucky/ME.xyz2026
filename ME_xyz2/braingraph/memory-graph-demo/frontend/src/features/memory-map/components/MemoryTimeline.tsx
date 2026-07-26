import type {GraphNode} from "../types/memoryGraph";
import styles from "../styles/memoryMap.module.css";

export function MemoryTimeline({events,value,onChange}:{events:GraphNode[];value:number;onChange:(value:number)=>void}){
  const times=events.flatMap(node=>node.eventTime?[new Date(node.eventTime).getTime()]:[]);
  const min=Math.min(...times),max=Math.max(...times);
  const current=Number.isFinite(value)?value:max;
  const visible=times.filter(time=>time<=current).length;
  return <section className={styles.timelineCard}><div className={styles.analyticsTitle}><b>记忆时间线</b><span>显示 {visible} / {times.length} 个事件</span></div>
    <div className={styles.timelineDate}>{new Date(current).toLocaleDateString("zh-CN",{year:"numeric",month:"long",day:"numeric"})}</div>
    <input aria-label="记忆时间线" className={styles.timelineRange} type="range" min={min} max={max} step={86400000} value={current} onChange={event=>onChange(Number(event.target.value))}/>
    <div className={styles.timelineLabels}><span>{new Date(min).toLocaleDateString("zh-CN")}</span><span>拖动以增补记忆节点</span><span>{new Date(max).toLocaleDateString("zh-CN")}</span></div>
  </section>;
}
