# 그래프를 다른 뷰로 추출 (export: mermaid/dot/json/graphml + 스코프)

`eb.py`에 `export` 명령을 추가해 그래프를 엑셀/시트가 아닌 **다른 뷰**로 뽑는다 — `--format mermaid`(깃허브 마크다운에 바로 렌더) · `dot`(Graphviz) · `json`(d3/cytoscape.js/sigma.js) · `graphml`(**Gephi** 등 전문 대규모 분석 도구). 전부 stdlib only·결정적이라 단위테스트로 박제한다. 끊긴 엣지(없는 노드 참조)는 뷰에서 제외한다.

**대규모 대응**: mermaid는 수백 노드부터 GitHub 렌더 한도·가독성에서 부적합하다. 그래서 (1) `--center <id> --depth N` 으로 **서브그래프만**(neighbors 스코프) 뽑아 mermaid를 작게 유지하고, (2) 전체 분석은 `graphml`→Gephi, `json`→sigma.js/cytoscape.js, `dot`→Graphviz sfdp 같은 **전문 툴**에 위임한다. "전체를 그리지 말고 쿼리 결과를 본다"가 원칙.

## 왜

- 초기 PRD는 시각화 export를 "v1 이후"로 미뤘다. 사용자가 "엑셀 말고 다른 뷰"를 원해 추가한다.
- "CSV가 원천, 나머지는 파생 뷰" 원칙에 정확히 부합한다 — export는 시트 동기화와 같은 **읽기 전용 단방향 파생**이다.
- **Mermaid 우선**: 깃허브 README/이슈에 ```mermaid 블록으로 붙이면 즉시 렌더돼, 별도 도구 없이 그래프를 "본다". DOT/JSON은 외부 렌더러·뷰어용.

## Consequences

- 코어 stdlib only 유지(렌더는 보는 쪽 도구). 결정적이라 mermaid/dot/json 출력 구조를 테스트로 보호.
- `samples/README.md`에 실제 ```mermaid 미리보기를 박아 뷰를 시연한다. 벤더된 `samples/eb.py` 스냅샷은 export 지원 버전으로 갱신한다.
