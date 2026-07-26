import {useCallback,useEffect,useMemo,useState} from "react";
import {MemoryGraphApi} from "../api/memoryGraphApi";
import type {GraphResponse,MemoryGraphApiConfig} from "../types/memoryGraph";
export function useMemoryGraph(config:MemoryGraphApiConfig,filters:Record<string,string|undefined>){
 const api=useMemo(()=>new MemoryGraphApi(config),[config]);const [data,setData]=useState<GraphResponse>();const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 const reload=useCallback(async()=>{setLoading(true);setError("");try{setData(await api.graph({...filters,limit:"300"}))}catch(e){setError(e instanceof Error?e.message:"加载失败")}finally{setLoading(false)}},[api,filters]);
 useEffect(()=>{void reload()},[reload]);return{api,data,error,loading,reload}
}
