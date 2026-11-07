export interface User {id:number;name:string;role:'ADMIN'|'STAFF'}
export type CategoryCode = 'MAINS'|'SNACKS'|'DRINKS'|'BEER';
export interface Option {id:number;name:string;price:number;is_default:boolean;unit_price?:number|null;bottles?:number;enabled?:boolean;incompatible_with?:number[]}
export interface Group {id:number;name:string;minimum:number;maximum:number;options:Option[]}
export interface MenuItem {id:number;name:string;base_price:number;groups:Group[];sku?:string;category_code?:CategoryCode;description?:string;complimentary?:boolean;verification_required?:boolean;verification_note?:string}
export interface Line {id:number;name:string;quantity:number;base_price:number;unit_price:number;line_total:number;status:string;modifiers:{name:string;price:number;option_id:number}[];description?:string;variant_name?:string;physical_bottles?:number;notes?:string;category_code?:CategoryCode}
export interface Batch {id:number;status:string;user_id:number;created_at:string;submitted_at:string|null;items:Line[]}
export interface Table {id:number;name:string;status:'AVAILABLE'|'OCCUPIED'|'PAYMENT_PENDING';session_id:number|null;opened_at:string|null;first_order_at?:string|null;total:number;item_count:number}
export interface Bill {session_id:number;table:string;status:string;items:Line[];total:number;item_count:number;has_drafts:boolean;opened_at?:string;first_order_at?:string|null;paid_at?:string|null;closed_at?:string|null;dining_duration_seconds?:number|null}
export interface PrintJob {id:number;batch_id:number|null;status:string;attempts:number;reprint:boolean;error:string|null;preview:string|null;created_at:string;routing_group?:string}
export interface Printer {mode:'mock'|'network';simulation:'success'|'connection_failure'|'timeout'|'uncertain';host:string;port:number;print_mode:'raster'|'text';encoding:string;profile:string;raster_command:'bitImageRaster'|'graphics'|'bitImageColumn';width:number;feed:number;cutter:boolean;separate_stations?:boolean;kitchen_host?:string;kitchen_port?:number;beverage_host?:string;beverage_port?:number}
export interface Payment {id:number;session_id:number;total:number;received:number;change:number;method:string;created_at:string}
export interface Transaction extends Payment {bill:Bill}
export interface Daily {date:string;total:number;transactions:number;methods:Record<string,number>;completed_sessions:number;category_sales:Record<CategoryCode,number>;average_spending:number;dining_duration:{count:number;average_seconds:number|null;minimum_seconds:number|null;maximum_seconds:number|null};beer_units:number;beer_bottles:number}
