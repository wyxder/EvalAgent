/**
 * rc-upload 4.11.0 ships without compiled .d.ts files, while antd's UploadProps
 * still imports `rc-upload/lib/interface`. Without this shim TypeScript resolves
 * RcUploadProps to `any`, and `Pick<any, 'capture' | 'hasControlInside' |
 * 'pastable'>` turns those fields into required props. Keep this declaration
 * minimal and aligned with the public props used by antd.
 */
declare module 'rc-upload/lib/interface' {
  export interface RcFile extends File {
    uid: string;
  }

  export interface UploadRequestOption<T = any> {
    action?: string;
    method?: string;
    data?: Record<string, any>;
    filename?: string;
    file?: RcFile;
    headers?: Record<string, string>;
    withCredentials?: boolean;
    onProgress?: (event: { percent?: number }) => void;
    onError?: (event: Error, body?: T) => void;
    onSuccess?: (body: T, xhr?: any) => void;
    [key: string]: any;
  }

  export interface UploadProps<T = any> {
    capture?: boolean | 'user' | 'environment';
    hasControlInside?: boolean;
    pastable?: boolean;
    [key: string]: any;
  }
}
