import { clone, hash } from './common.js'

export class Replay {
  constructor() {
    this.shapes = new Map(); this.blobs = new Map(); this.requests = new Map()
    this.order = []; this.errors = []; this.compactions = 0
  }
  key(session, id) { return session + '\0' + id }
  async feed(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) throw new Error('Invalid JSONL record')
    const session = record.sessionId || '', type = record.type
    if (type === 'api-request-shape') {
      if (await hash(record.shape) !== record.shapeHash) throw new Error('Shape digest mismatch')
      this.shapes.set(this.key(session, record.shapeHash), record.shape)
    }
    if (type === 'api-request-blob') {
      if (await hash(record.message) !== record.hash) throw new Error('Message digest mismatch')
      this.blobs.set(this.key(session, record.hash), record.message)
    } else if (record.message && typeof record.message === 'object' && typeof record.message.role === 'string' && 'content' in record.message) {
      const msg = { role: record.message.role, content: clone(record.message.content) }
      if (typeof msg.content === 'string') msg.content = [{ type: 'text', text: msg.content }]
      this.blobs.set(this.key(session, await hash(msg)), msg)
    }
    if (type === 'api-request') {
      if (typeof record.id !== 'string' || !record.id) throw new Error('Missing request id')
      const key = this.key(session, record.id)
      if (this.requests.has(key) && JSON.stringify(this.requests.get(key)) !== JSON.stringify(record)) throw new Error('Conflicting request id')
      if (!this.requests.has(key)) this.order.push(key)
      this.requests.set(key, record)
    }
    if (type === 'system' && record.subtype === 'compact_boundary') this.compactions++
  }
  refs(key) {
    const chain = [], seen = new Set()
    while (key) {
      if (seen.has(key)) throw new Error('Cyclic request base')
      seen.add(key)
      const r = this.requests.get(key)
      if (!r) throw new Error('Missing base request')
      chain.push(r)
      key = r.base ? this.key(r.sessionId || '', r.base) : null
    }
    let refs = []
    for (const r of chain.reverse()) {
      if (!Number.isInteger(r.keep) || r.keep < 0 || r.keep > refs.length || !Array.isArray(r.tail) || r.tail.some(x => typeof x !== 'string')) throw new Error('Invalid request delta')
      refs = refs.slice(0, r.keep).concat(r.tail)
    }
    return refs
  }
  async reconstruct(key) {
    if (this.errors.length) throw new Error('Invalid records; reconstruction integrity is unknown')
    const r = this.requests.get(key)
    if (!r) throw new Error('Missing request')
    const session = r.sessionId || '', shape = this.shapes.get(this.key(session, r.shapeHash))
    if (!shape || !r.params || !Array.isArray(r.cacheControl)) throw new Error('Unknown trace schema or missing shape')
    const body = clone({ ...r.params, ...shape })
    body.messages = this.refs(key).map(id => {
      const msg = this.blobs.get(this.key(session, id))
      if (!msg) throw new Error('Missing message dependency')
      return clone(msg)
    })
    for (const overlay of r.cacheControl) {
      if (!Array.isArray(overlay.path)) throw new Error('Invalid cache overlay')
      let target = body
      for (const segment of overlay.path) {
        if (Array.isArray(target)) {
          if (!Number.isInteger(segment) || segment < 0 || segment >= target.length) throw new Error('Invalid overlay index')
        } else if (!target || typeof target !== 'object' || typeof segment !== 'string' || !Object.hasOwn(target, segment)) throw new Error('Invalid overlay path')
        target = target[segment]
      }
      if (!target || typeof target !== 'object' || Array.isArray(target)) throw new Error('Invalid overlay target')
      target.cache_control = clone(overlay.value)
    }
    if (await hash(body) !== r.requestDigest) throw new Error('Request digest mismatch or unsupported schema')
    return { id: r.id, version: r.version, timestamp: r.timestamp, querySource: r.querySource, request: body }
  }
}
