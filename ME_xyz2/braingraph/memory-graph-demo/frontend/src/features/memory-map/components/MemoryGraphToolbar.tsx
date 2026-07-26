import {useEffect,useRef,useState} from "react";
import styles from "../styles/memoryMap.module.css";
import type {GraphNode} from "../types/memoryGraph";
export interface Filters{search:string;branch_id:string;emotion_code:string;start_time:string;end_time:string}
export function MemoryGraphToolbar({filters,setFilters,identities,emotions,onIdentityChange,onEmotionChange,onFit,onExit,showEmotionLinks,setShowEmotionLinks,showEventLinks,setShowEventLinks}:{filters:Filters;setFilters:(f:Filters)=>void;identities:GraphNode[];emotions:GraphNode[];onIdentityChange:(id:string)=>void;onEmotionChange:(id:string)=>void;onFit:()=>void;onExit:()=>void;showEmotionLinks:boolean;setShowEmotionLinks:(v:boolean)=>void;showEventLinks:boolean;setShowEventLinks:(v:boolean)=>void}){
 const set=(key:keyof Filters,value:string)=>setFilters({...filters,[key]:value});
 const [viewMenuOpen,setViewMenuOpen]=useState(false);
 const viewMenuRef=useRef<HTMLDivElement>(null);
 useEffect(()=>{
   if(!viewMenuOpen)return;
   const onDocClick=(e:MouseEvent)=>{
     if(viewMenuRef.current&&!viewMenuRef.current.contains(e.target as Node))setViewMenuOpen(false);
   };
   document.addEventListener("mousedown",onDocClick);
   return()=>document.removeEventListener("mousedown",onDocClick);
 },[viewMenuOpen]);
 return <header className={styles.toolbar}>
  <button type="button" className={styles.meBrand} onClick={onExit} aria-label="返回聊天">ME.xyz</button>

  <div className={styles.toolbarGroup}>
    <input className={styles.search} placeholder="搜索事件或观点或情绪" value={filters.search} onChange={e=>set("search",e.target.value)}/>
  </div>

  <div className={`${styles.toolbarGroup} ${styles.toolbarGroupCard}`}>
    <label className={styles.selectField}><small>身份</small><select aria-label="身份" value={filters.branch_id} onChange={e=>onIdentityChange(e.target.value)}>
      <option value="">未来的我</option>{identities.map(identity=><option key={identity.id} value={identity.branchId}>{identity.label}</option>)}
    </select></label>
    <label className={styles.selectField}><small>情绪</small><select aria-label="情绪" value={filters.emotion_code} onChange={e=>onEmotionChange(e.target.value)}>
      <option value="">情绪</option>{emotions.map(emotion=><option key={emotion.id} value={emotion.id.replace("emotion:","")}>{emotion.label}</option>)}
    </select></label>
    <label className={styles.dateField}><small>选择开始日期</small><input aria-label="开始日期" type="date" value={filters.start_time} onChange={e=>set("start_time",e.target.value)}/></label>
    <label className={styles.dateField}><small>选择结束日期</small><input aria-label="结束日期" type="date" value={filters.end_time} onChange={e=>set("end_time",e.target.value)}/></label>
  </div>

  <div className={styles.toolbarSpacer}/>

  <div className={styles.viewMenuWrap} ref={viewMenuRef}>
    <button type="button" className={styles.viewMenuTrigger} onClick={()=>setViewMenuOpen(v=>!v)} aria-label="视图设置">
      <i className="ph ph-sliders-horizontal"/>视图
    </button>
    {viewMenuOpen&&<div className={styles.viewMenuPanel}>
      <button type="button" className={styles.viewMenuItem} onClick={()=>{onFit();setViewMenuOpen(false);}}>
        <i className="ph ph-arrows-out"/>适配视图
      </button>
      <label className={styles.viewMenuToggle}>
        <input type="checkbox" checked={showEmotionLinks} onChange={e=>setShowEmotionLinks(e.target.checked)}/>情绪连线
      </label>
      <label className={styles.viewMenuToggle}>
        <input type="checkbox" checked={showEventLinks} onChange={e=>setShowEventLinks(e.target.checked)}/>事件连线
      </label>
    </div>}
  </div>
  </header>
}
