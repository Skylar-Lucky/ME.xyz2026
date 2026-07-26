import styles from "../styles/memoryMap.module.css";
export function GraphEmptyState({message,retry}:{message:string;retry?:()=>void}){return <div className={styles.state}><strong>{message}</strong>{retry&&<button onClick={retry}>重试</button>}</div>}
