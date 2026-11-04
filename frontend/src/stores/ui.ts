import {create} from 'zustand';
export const useUI = create<{notice:string;setNotice:(notice:string)=>void}>(set=>({notice:'',setNotice:notice=>set({notice})}));
