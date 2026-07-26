import type {EventDetail,GraphNode} from "../types/memoryGraph";
import styles from "../styles/memoryMap.module.css";

interface MemoryNodePanelProps{
  node?:GraphNode;
  detail?:EventDetail;
  loading:boolean;
  branchReport?:string;
  onClose:()=>void;
}

export function MemoryNodePanel({
  node,detail,loading,branchReport,onClose,
}:MemoryNodePanelProps){
  return <aside className={`${styles.panel} ${!node?styles.panelCollapsed:""}`}>
    <section className={styles.detailSlot}>
      {!node?<div className={styles.panelHint}><i className="ph ph-cursor-click"/><span>点击事件、身份或情绪查看详情</span></div>:<>
        <button className={styles.close} onClick={onClose} aria-label="关闭"><i className="ph ph-x"/></button>
        {node.type==="branch_anchor"?<>
          <span className={styles.eyebrow}>身份成长报告</span>
          <h2>{node.label}</h2>
          <div className={styles.growthReport}>{branchReport}</div>
        </>:node.type!=="event"?<>
          <span className={styles.eyebrow}>{node.type==="viewpoint"?"事件观点":"节点文档"}</span>
          <h2>{node.type==="viewpoint"?"观点记录":node.label}</h2>
          <p>{node.type==="viewpoint"?node.content:
            node.type==="emotion"?"连接不同人生分支中的共同感受。":
            "个人记忆网络的中心。"}</p>
        </>:loading?<p>正在读取详情…</p>:detail&&<>
          <span className={styles.eyebrow}>{detail.persona_name??(detail.branch_id==="main"?"主线记忆":"人物分支")}</span>
          <h2>{detail.event_content}</h2>
          <dl>
            <dt>发生时间</dt><dd>{new Date(detail.event_time).toLocaleDateString("zh-CN")}</dd>
            <dt>情绪</dt><dd>{detail.emotions.map(emotion=>
              <span className={styles.pill} key={emotion.code}>{emotion.label} {Math.round(emotion.intensity*100)}%</span>)}</dd>
            <dt>观点</dt><dd>{detail.viewpoint}</dd>
          </dl>
          <div className={styles.growthSection}>
            <span className={styles.eyebrow}>截至当前事件的成长与心路历程</span>
            <div className={styles.growthReport}>{detail.growth_summary}</div>
          </div>
        </>}
      </>}
    </section>
  </aside>;
}
