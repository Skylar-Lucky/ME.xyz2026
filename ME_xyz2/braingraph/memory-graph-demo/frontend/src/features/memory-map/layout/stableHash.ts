export function stableHash(value:string){let hash=2166136261;for(let i=0;i<value.length;i++){hash^=value.charCodeAt(i);hash=Math.imul(hash,16777619)}return hash>>>0}
export function branchAngle(branch:string){return branch==="main"?-Math.PI/2:(stableHash(branch)%360)*Math.PI/180}
