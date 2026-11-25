export interface AsyncState<T> {
  data: T;
  loading: boolean;
  error: string | null;
}

export const createAsyncState = <T>(data: T): AsyncState<T> => ({
  data,
  loading: true,
  error: null,
});
