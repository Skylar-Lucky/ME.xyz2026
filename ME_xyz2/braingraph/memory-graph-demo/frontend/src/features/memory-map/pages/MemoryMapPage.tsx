import {useEffect,useMemo,useState} from "react";
import {EmotionTrendChart} from "../components/EmotionTrendChart";
import {GraphEmptyState} from "../components/GraphEmptyState";
import {MemoryGraphCanvas} from "../components/MemoryGraphCanvas";
import {MemoryGraphLegend} from "../components/MemoryGraphLegend";
import {MemoryGraphToolbar,type Filters} from "../components/MemoryGraphToolbar";
import {MemoryNodePanel} from "../components/MemoryNodePanel";
import {MemoryTimeline} from "../components/MemoryTimeline";
import {useMemoryGraph} from "../hooks/useMemoryGraph";
import {buildTimelineDimming} from "../layout/graphView";
import type {EventDetail,GraphNode,MemoryGraphApiConfig} from "../types/memoryGraph";
import styles from "../styles/memoryMap.module.css";

export interface MemoryMapPageProps{
  apiBaseUrl?:string;
  initialBranchId?:string;
  onOpenConversation?:(conversationId:string,sourceTurnId?:string)=>void;
  className?:string;
  getAuthHeaders?:MemoryGraphApiConfig["getAuthHeaders"];
}

const emptyFilters=(branch=""):Filters=>({
  search:"",branch_id:branch,emotion_code:"",start_time:"",end_time:"",
});

export function MemoryMapPage({
  apiBaseUrl=import.meta.env.VITE_API_BASE_URL??window.location.origin,
  initialBranchId="",className="",getAuthHeaders,
}:MemoryMapPageProps){
  const [filters,setFilters]=useState(()=>emptyFilters(initialBranchId));
  const query=useMemo(()=>({
    start_time:filters.start_time,end_time:filters.end_time,
  }),[filters.start_time,filters.end_time]);
  const config=useMemo(()=>({baseUrl:apiBaseUrl,getAuthHeaders}),[apiBaseUrl,getAuthHeaders]);
  const {api,data,error,loading,reload}=useMemoryGraph(config,query);
  const [selected,setSelected]=useState<GraphNode>();
  const [focusId,setFocusId]=useState<string>();
  const [detail,setDetail]=useState<EventDetail>();
  const [detailLoading,setDetailLoading]=useState(false);
  const [showEmotionLinks,setShowEmotionLinks]=useState(false);
  const [showEventLinks,setShowEventLinks]=useState(false);
  const [fit,setFit]=useState<()=>void>(()=>()=>{});
  const [timelineEnd,setTimelineEnd]=useState<number>();

  const events=useMemo(()=>data?.nodes.filter(node=>node.type==="event")??[],[data]);
  const identities=useMemo(()=>data?.nodes.filter(node=>node.type==="branch_anchor")??[],[data]);
  const emotions=useMemo(()=>data?.nodes.filter(node=>node.type==="emotion")??[],[data]);
  const dropdownFocusId=useMemo(()=>{
    if(filters.branch_id){
      return identities.find(identity=>identity.branchId===filters.branch_id)?.id;
    }
    if(filters.emotion_code){
      return emotions.find(emotion=>emotion.id===`emotion:${filters.emotion_code}`)?.id;
    }
    return undefined;
  },[emotions,filters.branch_id,filters.emotion_code,identities]);
  useEffect(()=>{
    if(filters.branch_id||filters.emotion_code)setFocusId(dropdownFocusId);
  },[dropdownFocusId,filters.branch_id,filters.emotion_code]);
  const timeBounds=useMemo(()=>{
    const values=events.flatMap(node=>node.eventTime?[new Date(node.eventTime).getTime()]:[]);
    return{min:Math.min(...values),max:Math.max(...values)};
  },[events]);
  useEffect(()=>{
    if(Number.isFinite(timeBounds.max))setTimelineEnd(timeBounds.max);
  },[timeBounds.max]);
  const timelineDimming=useMemo(()=>{
    if(!data)return undefined;
    return buildTimelineDimming(data.nodes,data.links,timelineEnd??timeBounds.max);
  },[data,timeBounds.max,timelineEnd]);

  useEffect(()=>{
    if(selected?.type!=="event"){
      setDetail(undefined);return;
    }
    setDetailLoading(true);
    api.detail(selected.id).then(setDetail).finally(()=>setDetailLoading(false));
  },[api,selected]);

  const branchEvents=useMemo(()=>selected?.type==="event"
    ?events.filter(event=>event.branchId===selected.branchId)
      .sort((a,b)=>new Date(a.eventTime??0).getTime()-new Date(b.eventTime??0).getTime())
    :[],[events,selected]);
  const selectedEventIndex=selected?.type==="event"
    ?branchEvents.findIndex(event=>event.id===selected.id):-1;
  const selectNode=(node?:GraphNode)=>{
    setSelected(node);
    if(dropdownFocusId){setFocusId(dropdownFocusId);return}
    if(!node){setFocusId(undefined);return}
    if(node.type==="event"){
      const anchor=data?.nodes.find(item=>item.type==="branch_anchor"&&item.branchId===node.branchId);
      setFocusId(anchor?.id??node.id);
    }else setFocusId(node.id);
  };
  const simulatedBranchReport=useMemo(()=>{
    if(selected?.type!=="branch_anchor")return undefined;
    const items=events.filter(event=>event.branchId===selected.branchId)
      .sort((a,b)=>new Date(a.eventTime??0).getTime()-new Date(b.eventTime??0).getTime());
    if(!items.length)return"该身份暂时还没有成长事件。";
    const first=items[0],last=items[items.length-1];
    const emotionLabels=[...new Set(items.flatMap(item=>item.emotions?.map(emotion=>emotion.label)??[]))];
    return `这条“${selected.label}”路径目前记录了 ${items.length} 个成长节点。从“${first.content}”开始，你逐步经历了${items.slice(1,-1).map(item=>`“${item.content}”`).join("、")}，并走到“${last.content}”。过程中出现了${emotionLabels.join("、")}等感受。整体轨迹显示，你在持续行动、接受反馈和重新理解选择的过程中，逐渐形成了更具体的判断；这是一份基于当前模拟事件生成的阶段性成长报告。`;
  },[events,selected]);

  useEffect(()=>{
    const queryText=filters.search.trim().toLocaleLowerCase();
    if(!queryText||!data){
      if(!dropdownFocusId)setFocusId(undefined);
      return;
    }
    const match=
      data.nodes.find(node=>node.type==="event"&&node.content?.toLocaleLowerCase().includes(queryText))??
      data.nodes.find(node=>node.type==="viewpoint"&&node.content?.toLocaleLowerCase().includes(queryText))??
      data.nodes.find(node=>node.type==="emotion"&&(
        node.label.toLocaleLowerCase().includes(queryText)||node.id.toLocaleLowerCase().includes(queryText)
      ));
    if(!match)return;
    const relatedEvent=match.type==="viewpoint"
      ?data.nodes.find(node=>node.id===match.id.replace("viewpoint:",""))
      :match;
    if(relatedEvent?.eventTime){
      const eventTime=new Date(relatedEvent.eventTime).getTime();
      setTimelineEnd(current=>Math.max(current??eventTime,eventTime));
    }
    setSelected(match);
    if(!dropdownFocusId)setFocusId(match.id);
  },[data,dropdownFocusId,filters.search]);

  const exitGraph=()=>{
    window.location.assign("/?goto=chat");
  };

  return <section className={`${styles.page} ${className}`}>
    <MemoryGraphToolbar filters={filters} setFilters={setFilters} identities={identities} emotions={emotions}
      onExit={exitGraph}
      onIdentityChange={branchId=>{
        setFilters({...filters,branch_id:branchId,emotion_code:""});
        const identity=branchId?identities.find(item=>item.branchId===branchId):undefined;
        setSelected(identity);
        setFocusId(identity?.id);
      }}
      onEmotionChange={emotionCode=>{
        setFilters({...filters,emotion_code:emotionCode,branch_id:""});
        const emotion=emotionCode?emotions.find(item=>item.id===`emotion:${emotionCode}`):undefined;
        setSelected(emotion);
        setFocusId(emotion?.id);
      }}
      onFit={fit}
      showEmotionLinks={showEmotionLinks} setShowEmotionLinks={setShowEmotionLinks}
      showEventLinks={showEventLinks} setShowEventLinks={setShowEventLinks}/>
    <div className={styles.pageBody}>
      <div className={styles.mainColumn}>
        <main className={styles.workspace}>
          <div className={styles.canvas}>
            {loading?<GraphEmptyState message="正在整理你的记忆网络…"/>:
              error?<GraphEmptyState message={error} retry={()=>void reload()}/>:
              !data?.nodes.length?<GraphEmptyState message="没有符合条件的记忆"/>:
              <MemoryGraphCanvas nodes={data.nodes} links={data.links}
                selectedId={selected?.id} focusId={focusId}
                dimNodeIds={timelineDimming?.dimNodeIds} dimLinkIds={timelineDimming?.dimLinkIds}
                onSelect={selectNode}
                showEmotionLinks={showEmotionLinks} showEventLinks={showEventLinks}
                onReady={handler=>setFit(()=>handler)}/>}
            {selected?.type==="event"&&<div className={styles.eventNavigation}>
              <button disabled={selectedEventIndex<=0} onClick={()=>selectNode(branchEvents[selectedEventIndex-1])}><i className="ph ph-caret-left"/>上一事件</button>
              <button disabled={selectedEventIndex<0||selectedEventIndex>=branchEvents.length-1} onClick={()=>selectNode(branchEvents[selectedEventIndex+1])}>下一事件<i className="ph ph-caret-right"/></button>
            </div>}
            {data&&<div className={styles.stats}><b>{timelineDimming?.visibleEventCount??0}</b> 个已发生事件 · {data.stats.branchCount} 条人生线 · {data.stats.emotionCount} 种情绪</div>}
          </div>
        </main>
        {events.length>0&&Number.isFinite(timeBounds.max)&&<div className={styles.analyticsDock}>
          <EmotionTrendChart events={events} currentTime={timelineEnd??timeBounds.max}/>
          <MemoryTimeline events={events} value={timelineEnd??timeBounds.max} onChange={value=>{
            setTimelineEnd(value);setSelected(undefined);
            if(!dropdownFocusId)setFocusId(undefined);
          }}/>
        </div>}
        <MemoryGraphLegend
          showEventLinks={showEventLinks} onToggleEventLinks={()=>setShowEventLinks(v=>!v)}
          showEmotionLinks={showEmotionLinks} onToggleEmotionLinks={()=>setShowEmotionLinks(v=>!v)}/>
      </div>
      <MemoryNodePanel node={selected} detail={detail} loading={detailLoading}
        branchReport={simulatedBranchReport}
        onClose={()=>{setSelected(undefined);if(!dropdownFocusId)setFocusId(undefined)}}/>
    </div>
  </section>;
}
