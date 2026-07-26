import styles from "../styles/memoryMap.module.css";

const NODE_ITEMS=[
  {shape:"circle",color:"#FF5FC8",size:14,label:"我"},
  {shape:"circle",color:"#4DCAFF",size:10,label:"事件"},
  {shape:"circle",color:"#C77EFF",size:12,label:"人物形象"},
  {shape:"diamond",color:"#FFE66E",size:10,label:"共享情绪"},
  {shape:"square",color:"#58F287",size:9,label:"观点"},
];

export interface MemoryGraphLegendProps{
  showEventLinks:boolean;
  onToggleEventLinks:()=>void;
  showEmotionLinks:boolean;
  onToggleEmotionLinks:()=>void;
}

export function MemoryGraphLegend({
  showEventLinks,onToggleEventLinks,showEmotionLinks,onToggleEmotionLinks,
}:MemoryGraphLegendProps){
  return <div className={styles.legend}>
    {NODE_ITEMS.map(item=>
      <span key={item.label} className={styles.legendItem}>
        <i className={styles.legendShape} data-shape={item.shape}
          style={{background:item.color,width:item.size,height:item.size,boxShadow:`0 0 6px ${item.color}99`}}/>
        {item.label}
      </span>
    )}
    <button type="button" className={`${styles.legendItem} ${styles.legendItemButton}`}
      data-active={showEventLinks} onClick={onToggleEventLinks}
      title={showEventLinks?"点击隐藏事件边":"点击显示事件边"}>
      <i className={styles.legendLine} data-style="solid" style={{borderColor:"#C77EFF"}}/>
      事件边
    </button>
    <button type="button" className={`${styles.legendItem} ${styles.legendItemButton}`}
      data-active={showEmotionLinks} onClick={onToggleEmotionLinks}
      title={showEmotionLinks?"点击隐藏情绪边":"点击显示情绪边"}>
      <i className={styles.legendLine} data-style="dashed" style={{borderColor:"#FFE66E"}}/>
      情绪边
    </button>
    <span className={styles.legendItem}>
      <i className={styles.legendLine} data-style="dotted" style={{borderColor:"#58F287"}}/>
      观点边
    </span>
  </div>;
}
