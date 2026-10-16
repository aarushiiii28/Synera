// Recorded-demo mode. When the site is built with VITE_STATIC=1 there is no API: every call is answered from the
// JSON files that scripts/build_snapshot.py recorded from the real API. File names must match its `slug()`.
// Nothing is computed here: lists are filtered and sorted the way the server does it, and anything that would
// start a computation (run the engine, launch an attack, re-verify) replays the recorded outcome.

export const isStatic = import.meta.env.VITE_STATIC === '1';

type MkError = (status: number, code: string, message: string) => Error;

const slug = (s: string) => s.replace(/[^A-Za-z0-9.-]+/g, '_').replace(/^_+|_+$/g, '');
const keyOf = (path: string) => {
  const [p, q = ''] = path.split('?');
  const sorted = q ? q.split('&').sort().join('&') : '';
  return slug(p + (sorted ? `?${sorted}` : ''));
};

const cache = new Map<string, Promise<unknown>>();
function load<T>(name: string, mk: MkError): Promise<T> {
  let p = cache.get(name);
  if (!p) {
    p = fetch(`${import.meta.env.BASE_URL}snapshot/${name}.json`)
      .then(async (r) => {
        // Static hosts answer unknown paths with index.html (status 200), so check the content type too.
        if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) throw mk(404, 'NOT_RECORDED', 'This is not part of the recorded demo.');
        return r.json();
      })
      .catch((e) => {
        cache.delete(name);
        throw e instanceof Error && 'status' in e ? e : mk(0, 'NETWORK', 'The recorded demo data could not be loaded.');
      });
    cache.set(name, p);
  }
  return p as Promise<T>;
}

export const snapshotMeta = () => load<{ generated_at: string; ledger_height: number | null }>('meta', (s, c, m) => Object.assign(new Error(m), { status: s, code: c }));

/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = any;

const SORTS: Record<string, (a: Any, b: Any) => number> = {
  q_value: (a, b) => a.q_value - b.q_value, '-q_value': (a, b) => b.q_value - a.q_value,
  effect_size: (a, b) => a.effect_size - b.effect_size, '-effect_size': (a, b) => b.effect_size - a.effect_size,
  status: (a, b) => String(a.status).localeCompare(String(b.status)), created: () => 0,
};

async function listFindings(params: URLSearchParams, mk: MkError) {
  const all = await load<Any>('all_findings', mk);
  const q = (params.get('q') ?? '').toLowerCase();
  let items: Any[] = all.items.filter((f: Any) =>
    (!params.get('status') || f.status === params.get('status')) && (!params.get('track') || f.track === params.get('track')) &&
    (!params.get('type') || f.type === params.get('type')) && (!params.get('provenance') || f.provenance === params.get('provenance')) &&
    (!params.get('dataset_id') || f.dataset_id === params.get('dataset_id')) &&
    (!q || f.stressors.some((s: string) => s.toLowerCase().includes(q)) || (f.feature ?? '').toLowerCase().includes(q)));
  items = [...items].sort(SORTS[params.get('sort') ?? '-effect_size'] ?? SORTS['-effect_size']);
  const offset = Number(params.get('offset') ?? 0), limit = Number(params.get('limit') ?? 50);
  return { total: items.length, items: items.slice(offset, offset + limit), counts: all.counts };
}

async function listRuns(params: URLSearchParams, mk: MkError) {
  const all = await load<Any[]>('all_runs', mk);
  return all.filter((r) => (!params.get('dataset_id') || r.dataset_id === params.get('dataset_id')) && (!params.get('status') || r.status === params.get('status')));
}

async function listBlocks(params: URLSearchParams, mk: MkError) {
  const all = await load<Any>('all_blocks', mk);
  let items: Any[] = all.items.filter((b: Any) => !params.get('block_type') || b.block_type === params.get('block_type'));
  if (params.get('order') === 'desc') items = [...items].reverse();
  const offset = Number(params.get('offset') ?? 0), limit = Number(params.get('limit') ?? 50);
  return { total: items.length, items: items.slice(offset, offset + limit) };
}

async function searchGenes(params: URLSearchParams, mk: MkError) {
  const rows = await load<Any[][]>('all_genes', mk);
  const s = (params.get('search') ?? '').toLowerCase();
  const hit = rows.filter((r) => String(r[1]).toLowerCase().includes(s) || String(r[0]).toLowerCase().includes(s) || String(r[2]).toLowerCase().includes(s));
  const offset = Number(params.get('offset') ?? 0), limit = Number(params.get('limit') ?? 200);
  const items = hit.slice(offset, offset + limit).map((r) => ({
    ensembl_id: r[0], gene_symbol: r[1], name: r[2], b_AB: r[3], p: r[4], q: r[5], neg_log10_p: r[6], neg_log10_q: r[7], type: r[8],
    replication_b_AB: r[9], replication_p: r[10], same_sign_in_replication: r[11], passed_filter_both: r[12],
  }));
  return { total: hit.length, items };
}

export async function snapshotReq<T>(path: string, init: RequestInit | undefined, mk: MkError): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase();
  const [p, query = ''] = path.split('?');
  const params = new URLSearchParams(query);

  if (method === 'POST') {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (p === '/runs') {
      // "Run the engine": replay the latest recorded completed run for the dataset (the page shows it as a recorded run).
      const datasets = await load<Any[]>('datasets', mk);
      const ds = datasets.find((d) => d.id === body.dataset_id);
      if (!ds) throw mk(404, 'NOT_FOUND', `dataset '${body.dataset_id}' not found`);
      if (!ds.runnable) throw mk(400, 'NOT_RUNNABLE', `'${body.dataset_id}' has no outcome variable`);
      const run = (await load<Any[]>('all_runs', mk)).find((r) => r.dataset_id === body.dataset_id && r.status === 'COMPLETED');
      if (!run) throw mk(404, 'NOT_RECORDED', 'No recorded run for this dataset.');
      return { run_id: run.id, reused: true } as T;
    }
    let m = p.match(/^\/datasets\/([^/]+)\/verify$/);
    if (m) return load<T>(`verify_dataset_${slug(m[1])}`, mk);
    m = p.match(/^\/findings\/([^/]+)\/verify$/);
    if (m) return load<T>(`verify_finding_${slug(m[1])}`, mk);
    if (p === '/security/simulate-tamper') return load<T>(`tamper_${slug(body.dataset_id ?? '')}_${slug(body.mode ?? '')}`, mk);
    throw mk(404, 'NOT_RECORDED', 'This action is not part of the recorded demo.');
  }

  if (p === '/findings') return listFindings(params, mk) as Promise<T>;
  if (p === '/runs') return listRuns(params, mk) as Promise<T>;
  if (p === '/ledger/blocks') return listBlocks(params, mk) as Promise<T>;
  let m = p.match(/^\/ledger\/blocks\/(\d+)$/);
  if (m) {
    const b = (await load<Any>('all_blocks', mk)).items.find((x: Any) => x.index === Number(m![1]));
    if (!b) throw mk(404, 'NOT_FOUND', `block ${m[1]} not found`);
    return b as T;
  }
  m = p.match(/^\/ledger\/proof\/([0-9a-f]+)$/);
  if (m) return load<T>(`ledger_proof_${m[1]}`, mk);
  if (p === '/space-biology/genes' && params.get('search')) return searchGenes(params, mk) as Promise<T>;
  return load<T>(keyOf(path), mk);
}
