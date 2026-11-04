export interface User {id:number;name:string;role:'ADMIN'|'STAFF'}
export interface Option {id:number;name:string;price:number;is_default:boolean}
export interface Group {id:number;name:string;minimum:number;maximum:number;options:Option[]}
export interface MenuItem {id:number;name:string;base_price:number;groups:Group[]}
export interface Line {id:number;name:string;quantity:number;base_price:number;unit_price:number;line_total:number;status:string;modifiers:{name:string;price:number;option_id:number}[]}
export interface Batch {id:number;status:string;user_id:number;created_at:string;submitted_at:string|null;items:Line[]}
export interface Table {id:number;name:string;status:'AVAILABLE'|'OCCUPIED'|'PAYMENT_PENDING';session_id:number|null;opened_at:string|null;total:number;item_count:number}
export interface Bill {session_id:number;table:string;status:string;items:Line[];total:number;item_count:number;has_drafts:boolean}
export interface PrintJob {id:number;batch_id:number|null;status:string;attempts:number;reprint:boolean;error:string|null;preview:string|null;created_at:string}
export interface Printer {mode:'mock'|'network';simulation:'success'|'connection_failure'|'timeout'|'uncertain';host:string;port:number;print_mode:'raster'|'text';encoding:string;profile:string;raster_command:'bitImageRaster'|'graphics'|'bitImageColumn';width:number;feed:number;cutter:boolean}
export interface Payment {id:number;session_id:number;total:number;received:number;change:number;method:string;created_at:string}
export interface Transaction extends Payment {bill:Bill}
export interface Daily {date:string;total:number;transactions:number;methods:Record<string,number>}
