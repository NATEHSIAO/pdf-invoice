interface IDBDatabase {
  transaction(storeNames: string | string[], mode?: IDBTransactionMode): IDBTransaction;
  createObjectStore(name: string, options?: IDBObjectStoreParameters): IDBObjectStore;
  objectStoreNames: DOMStringList;
}

interface IDBObjectStore {
  createIndex(name: string, keyPath: string | string[], options?: IDBIndexParameters): IDBIndex;
  index(name: string): IDBIndex;
  put(value: any, key?: IDBValidKey): IDBRequest;
  delete(key: IDBValidKey | IDBKeyRange): IDBRequest;
  clear(): IDBRequest;
  getAll(query?: IDBValidKey | IDBKeyRange | null, count?: number): IDBRequest;
}

interface IDBIndex {
  openCursor(range?: IDBValidKey | IDBKeyRange | null, direction?: IDBCursorDirection): IDBRequest;
  getAll(query?: IDBValidKey | IDBKeyRange | null, count?: number): IDBRequest;
}

interface IDBCursor {
  delete(): IDBRequest;
  continue(): void;
  value: any;
}

interface IDBRequest<T = any> {
  result: T;
  error: DOMException | null;
  source: IDBObjectStore | IDBIndex | IDBCursor;
  transaction: IDBTransaction;
  onerror: ((this: IDBRequest<T>, ev: Event) => any) | null;
  onsuccess: ((this: IDBRequest<T>, ev: Event) => any) | null;
}

interface IDBOpenDBRequest extends IDBRequest {
  onupgradeneeded: ((this: IDBOpenDBRequest, ev: IDBVersionChangeEvent) => any) | null;
}

interface IDBVersionChangeEvent extends Event {
  oldVersion: number;
  newVersion: number | null;
}

declare global {
  interface Window {
    indexedDB: IDBFactory;
  }
} 