import {api} from './client.js';
export const syncApi={
  status:()=>api('/sync/status'),
  bootstrap:()=>api('/sync/bootstrap','POST',{}),
  pull:limit=>api('/sync/pull','POST',{limit:limit||100}),
  reset:()=>api('/sync/reset','POST',{}),
  overview:()=>api('/review/overview'),
  relations:()=>api('/review/relations'),
  dependencies:()=>api('/review/dependencies'),
  commits:()=>api('/review/commits')
};
