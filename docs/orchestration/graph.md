# Planned orchestration graph

Example plan only; not live T3 state, scheduling, or merge authorization.

| Node | Title | Status | Dependencies | Exclusive ownership | Readiness / blockers |
| --- | --- | --- | --- | --- | --- |
| builder&#45;a | Build calculator changes | planned | &#40;none&#41; | src&#47;agent&#95;workflow&#95;pilot&#47;calculator&#46;py&#44; tests&#47;test&#95;calculator&#46;py | ready |
| builder&#45;b | Build statistics changes | planned | &#40;none&#41; | src&#47;agent&#95;workflow&#95;pilot&#47;statistics&#46;py&#44; tests&#47;test&#95;statistics&#46;py | ready |
| delivery | Controller verifies protections and delivers | planned | review | &#40;none&#41; | dependency builder&#45;a&#58; planned&#59; dependency builder&#45;b&#58; planned&#59; dependency review&#58; planned |
| review | Independent review of exact combined head | planned | builder&#45;a&#44; builder&#45;b | &#40;none&#41; | dependency builder&#45;a&#58; planned&#59; dependency builder&#45;b&#58; planned |
