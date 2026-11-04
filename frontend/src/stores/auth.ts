import { create } from 'zustand';
import type {User} from '../services/types';
interface Auth {token:string|null;user:User|null;signIn:(token:string,user:User)=>void;signOut:()=>void}
export const useAuth = create<Auth>(set=>({token:sessionStorage.getItem('koko-token'),user:null,
  signIn:(token,user)=>{sessionStorage.setItem('koko-token',token);set({token,user});},
  signOut:()=>{sessionStorage.removeItem('koko-token');set({token:null,user:null});}}));
