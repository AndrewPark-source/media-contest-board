#!/usr/bin/env python3
"""공모전 보드(index.html)의 DATA 배열 관리 도구.

사용법 (저장소 루트에서 실행):
  python3 tools/merge_entries.py --list
      현재 등록된 항목을 '마감일 | 제목 | 링크' 로 출력 (중복 확인용)
  python3 tools/merge_entries.py new_entries.js [--extend "제목 일부=YYYY-MM-DD" ...]
      new_entries.js 의 항목을 추가하고 마감일순 정렬, 월 구분 주석 재생성, node 로 검증.
      제목이나 링크가 이미 있는 항목은 건너뜀. 검증 실패 시 index.html 을 원상복구하고 종료코드 1.
  python3 tools/merge_entries.py --extend "제목 일부=YYYY-MM-DD"
      기존 항목의 마감일만 변경 (접수기간 연장 반영). 제목 일부는 정확히 1건에만 일치해야 함.

new_entries.js 형식 (항목마다 '  { n: ' 로 시작, 한 항목은 여러 줄 가능, 문자열 안에 큰따옴표 금지):
  { n: "제목", h: "주최", c: "video|ai|ad|photo|design|multi", d: "YYYY-MM-DD", e: "univ|youth|all",
    who: "응모자격", spec: "규격·접수방법", theme: "주제", prize: "짧은 상금", prizeFull: "상금 상세",
    link: "https://...", src: "출처" },
"""
import re, subprocess, sys, json, shutil, os

HTML = 'index.html'
HEAD = 'const DATA = [\n'
KOR = {'01': '1월', '02': '2월', '03': '3월', '04': '4월', '05': '5월', '06': '6월',
       '07': '7월', '08': '8월', '09': '9월', '10': '10월', '11': '11월', '12': '12월'}

def objs(t):
    t = re.sub(r'^\s*//.*$', '', t, flags=re.M)
    out = []
    for x in re.split(r'\n(?=  \{ n: )', t.strip('\n')):
        x = x.strip('\n')
        if not x.strip():
            continue
        x = x.rstrip().rstrip(',')
        m = re.search(r'd: "(\d{4}-\d{2}-\d{2})"', x)
        if not m:
            sys.exit('마감일(d) 형식 오류: ' + x[:80])
        out.append([m.group(1), x])
    return out

def field(x, k):
    m = re.search(r'\b%s: "([^"]*)"' % k, x)
    return m.group(1) if m else ''

def norm(s):
    return re.sub(r'[\s\W_]+', '', s).lower()

def main():
    args = sys.argv[1:]
    s = open(HTML, encoding='utf-8').read()
    start = s.index(HEAD) + len(HEAD)
    end = s.index('\n];', start)
    old = objs(s[start:end])

    if args == ['--list']:
        for d, x in old:
            print(d, '|', field(x, 'n'), '|', field(x, 'link'))
        print('총', len(old), '건', file=sys.stderr)
        return

    extends, files = [], []
    i = 0
    while i < len(args):
        if args[i] == '--extend':
            extends.append(args[i + 1]); i += 2
        else:
            files.append(args[i]); i += 1

    for e in extends:
        key, date = e.rsplit('=', 1)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
            sys.exit('날짜 형식 오류: ' + e)
        hit = [o for o in old if key in field(o[1], 'n')]
        if len(hit) != 1:
            sys.exit('--extend "%s" 는 %d건에 일치 (정확히 1건이어야 함)' % (key, len(hit)))
        hit[0][1] = re.sub(r'd: "\d{4}-\d{2}-\d{2}"', 'd: "%s"' % date, hit[0][1], count=1)
        print('마감일 변경:', field(hit[0][1], 'n'), hit[0][0], '->', date)
        hit[0][0] = date

    names = {norm(field(x, 'n')) for _, x in old}
    links = {field(x, 'link') for _, x in old}
    added, skipped = [], []
    for f in files:
        for d, x in objs(open(f, encoding='utf-8').read()):
            n, l = field(x, 'n'), field(x, 'link')
            if norm(n) in names or l in links:
                skipped.append(n); continue
            names.add(norm(n)); links.add(l); added.append([d, x])

    allx = sorted(old + added, key=lambda t: t[0])
    lines, cur = [], None
    for d, x in allx:
        ym = d[:7]
        if ym != cur:
            if cur is not None:
                lines.append('')
            label = KOR[d[5:7]] if d[:4] == '2026' else '%s년 %s' % (d[:4], KOR[d[5:7]])
            lines.append('  // ---------- %s ----------' % label)
            cur = ym
        lines.append(x + ',')
    shutil.copy(HTML, HTML + '.bak')
    open(HTML, 'w', encoding='utf-8').write(s[:start] + '\n'.join(lines) + s[end:])

    check = r"""
const fs=require('fs');const s=fs.readFileSync('index.html','utf8');
const a=s.indexOf('const DATA = [');const b=s.indexOf('\n];',a)+3;
const D=eval('('+s.slice(a+'const DATA = '.length,b-1)+')');
const C=new Set(['video','ai','ad','photo','design','multi']),E=new Set(['univ','youth','all']);
const req=['n','h','c','d','e','who','spec','theme','prize','prizeFull','link','src'];
const bad=D.filter(x=>req.some(k=>!x[k])||!C.has(x.c)||!E.has(x.e)||!/^\d{4}-\d{2}-\d{2}$/.test(x.d)||!/^https?:\/\//.test(x.link));
const sorted=D.every((x,i)=>i==0||D[i-1].d<=x.d);
console.log(JSON.stringify({total:D.length,bad:bad.map(x=>x.n||'?'),sorted}));
if(bad.length||!sorted)process.exit(1);
"""
    r = subprocess.run(['node', '-e', check], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.move(HTML + '.bak', HTML)
        print(r.stdout, r.stderr)
        sys.exit('검증 실패 — index.html 을 원상복구했습니다.')
    os.remove(HTML + '.bak')
    info = json.loads(r.stdout)
    print('기존', len(old), '추가', len(added), '건너뜀', len(skipped), '합계', info['total'])
    for n in skipped:
        print('  건너뜀(중복):', n)

if __name__ == '__main__':
    main()
