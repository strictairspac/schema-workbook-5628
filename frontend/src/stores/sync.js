import {syncApi} from '../api/sync.js';
export const syncStore={data:null,async refresh(){this.data=await syncApi.overview();return this.data;}};
