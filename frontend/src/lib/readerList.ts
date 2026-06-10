const READER_LIST_KEY = 'reader_list';

export function setReaderList(ids: string[]) {
  try {
    sessionStorage.setItem(READER_LIST_KEY, JSON.stringify({ ids }));
  } catch {
    // sessionStorage unavailable
  }
}

export function getReaderList(): { ids: string[] } | null {
  try {
    const raw = sessionStorage.getItem(READER_LIST_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as { ids: string[] };
  } catch {
    return null;
  }
}
