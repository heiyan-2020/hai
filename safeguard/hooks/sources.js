import { HAN, display, excerpt, strings } from './common.js'
const join = (base, rest) => base.replace(/[\\/]$/, '') + '/' + rest
const escape = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

async function matchFile($, path, anchor) {
  try {
    if (!await $.fs.exists(path) || (await $.fs.stat(path)).size > 524288) return null
    const text = await $.fs.read(path)
    if (!text.replace(/\s+/g, ' ').includes(anchor)) return null
    const found = new RegExp(anchor.split(/\s+/).map(escape).join('\\s+')).exec(text)
    return { file: path, line: found ? text.slice(0, found.index).split('\n').length : null }
  } catch { return null }
}

async function locate($, line, skill, cwd) {
  const flat = line.replace(/\s+/g, ' ').trim(), at = flat.search(HAN)
  const anchor = flat.slice(Math.max(0, at - 24), at + 49)
  if (anchor.length < 8) return []
  const home = await $.env.get('HOME') || await $.env.get('USERPROFILE')
  const root = await $.env.get('CLAUDE_CONFIG_DIR') || (home ? join(home, '.claude') : null)
  const candidates = []
  if (skill && root) {
    const pieces = skill.split(':'), name = pieces[pieces.length - 1]
    if (pieces.length > 1) {
      try {
        const registry = JSON.parse(await $.fs.read(join(root, 'plugins/installed_plugins.json')))
        for (const [id, entries] of Object.entries(registry.plugins || {})) {
          if (id.split('@')[0] !== pieces[0]) continue
          for (const entry of Array.isArray(entries) ? entries : [entries]) {
            if (!entry.installPath || (entry.projectPath && cwd !== entry.projectPath && !cwd.startsWith(entry.projectPath + '/'))) continue
            candidates.push(join(entry.installPath, 'skills/' + name + '/SKILL.md'), join(entry.installPath, 'commands/' + name + '.md'))
          }
        }
      } catch { /* Unknown registry format is not evidence of a source file. */ }
    } else {
      candidates.push(join(root, 'skills/' + name + '/SKILL.md'), join(root, 'commands/' + name + '.md'))
      candidates.push(join(cwd, '.claude/skills/' + name + '/SKILL.md'), join(cwd, '.claude/commands/' + name + '.md'))
    }
  } else {
    if (root) candidates.push(join(root, 'CLAUDE.md'))
    try {
      const ancestors = await $.fs.ancestors({ names: ['CLAUDE.md', 'CLAUDE.local.md', '.claude/CLAUDE.md'] })
      for (const source of ancestors) candidates.push(join(source.dir, source.name))
    } catch { /* Optional metadata may not exist on every host. */ }
  }
  const matches = []
  for (const path of [...new Set(candidates)].slice(0, 64)) {
    const found = await matchFile($, path, anchor)
    if (found) matches.push(found)
    if (matches.length >= 3) break
  }
  return matches
}

export async function diagnose($, body, cwd) {
  const findings = []
  for (const [path, text] of strings(body)) {
    if (!HAN.test(text)) continue
    const lines = text.split('\n')
    for (let i = 0; i < lines.length; i++) {
      if (!HAN.test(lines[i])) continue
      const named = /^\s*[-*]\s+([A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)*):\s+/.exec(lines[i])
      const skill = named ? named[1] : null
      const sources = await locate($, lines[i], skill, cwd)
      findings.push({ location: path, textLine: i + 1, skill, sources, excerpt: excerpt(lines[i]) })
      if (findings.length >= 3) return findings
    }
  }
  return findings
}

export function formatFinding(finding) {
  const lines = ['Location: ' + finding.location + ' (text line ' + finding.textLine + ')']
  if (finding.skill) lines.push('Skill: ' + finding.skill)
  if (finding.sources.length === 1) {
    const source = finding.sources[0]
    lines.push('Source file: ' + display(source.file) + (source.line ? ':' + source.line : '') + ' (text match)')
  } else if (finding.sources.length) {
    lines.push('Source file: ambiguous; matches: ' + finding.sources.map(s => display(s.file) + ':' + s.line).join(', '))
  } else lines.push('Source file: not identified')
  lines.push('Excerpt: ' + JSON.stringify(finding.excerpt))
  return lines.join('\n')
}
