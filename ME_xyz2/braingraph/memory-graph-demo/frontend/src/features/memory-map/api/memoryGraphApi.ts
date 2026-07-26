import type {EventDetail,GraphResponse,MemoryGraphApiConfig} from "../types/memoryGraph";
export class MemoryGraphApi {
  constructor(private config:MemoryGraphApiConfig){}
  private async request<T>(path:string,init?:RequestInit):Promise<T>{
    const headers=await this.config.getAuthHeaders?.()??{};
    const response=await fetch(`${this.config.baseUrl.replace(/\/$/,"")}/api${path}`,{...init,headers:{"Content-Type":"application/json",...headers}});
    if(!response.ok)throw new Error((await response.json().catch(()=>null))?.detail??`请求失败 (${response.status})`);
    return response.json() as Promise<T>;
  }
  graph(params:Record<string,string|undefined>){const q=new URLSearchParams(Object.entries(params).filter((x):x is [string,string]=>Boolean(x[1])));return this.request<GraphResponse>(`/memory-graph?${q}`)}
  detail(id:string){return this.request<EventDetail>(`/memory-events/${encodeURIComponent(id)}`)}
}
