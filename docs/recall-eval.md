# Recall evaluation

_Generated 2026-10-13T22:48+00:00 by `uv run python -m app.recall_eval run` over 178 saved solutions (177 problems). Do not edit by hand._

For each solved problem with a statement and at least one relative, retrieval ran over the user's own rows with the query's own row excluded — by topic tags and by embedding similarity, same rows, same k, the production similarity floor (0.35) — and the top k was scored against three label sets. **hit@k**: a relative in the top k. **recall@k**: share of the relatives in the top k. **MRR**: 1 / rank of the first relative.

- **LeetCode similar**: LeetCode's curated Similar Questions, either direction, among solved problems. External; mixes same-technique with same-series.
- **same pattern**: the saved solutions share a coarse pattern (one of 19). Big buckets; a hit says little.
- **same technique**: the saved solutions share a specific technique (one of 72, `app/recall_eval.py`). This is "solved similarly".
- **your technique works for it**: the technique the user used for the saved solution is one of the query problem's workable techniques — the labels of its generated approaches plus the user's own. Looser than same technique; closest to what the tutor needs.

Methods: **tags** (topic-tag overlap); **embeddings** (the problem's statement embedded, today's production recall); **hyde** (3 plausible approaches written by the summary model and embedded, a row scoring by its best match against any of them); **hyde + statement** (best match against the statement or any approach).

**Hand check:** of 16 LeetCode-similar pairs judged by hand, 13 (81%) are solved similarly by the definition above.

## LeetCode similar — n = 86 queries (86 of 177 solved problems have a relative; median relatives per query 1)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 21% | 44% | 49% | 16% | 38% | 42% | 0.32 |
| embeddings | 60% | 85% | 90% | 48% | 77% | 82% | 0.73 |
| embeddings, no floor | 62% | 87% | 92% | 49% | 80% | 85% | 0.74 |
| hyde | 60% | 83% | 91% | 49% | 75% | 84% | 0.73 |
| hyde + statement | 64% | 81% | 93% | 51% | 75% | 87% | 0.75 |

## same pattern — n = 174 queries (174 of 177 solved problems have a relative; median relatives per query 11)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 49% | 80% | 82% | 5% | 15% | 21% | 0.64 |
| embeddings | 63% | 83% | 86% | 6% | 15% | 22% | 0.73 |
| embeddings, no floor | 64% | 84% | 87% | 6% | 15% | 22% | 0.74 |
| hyde | 65% | 83% | 89% | 6% | 16% | 24% | 0.74 |
| hyde + statement | 68% | 84% | 89% | 7% | 16% | 24% | 0.76 |

## same technique — n = 153 queries (153 of 177 solved problems have a relative; median relatives per query 4)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 32% | 55% | 58% | 8% | 21% | 29% | 0.43 |
| embeddings | 45% | 65% | 71% | 14% | 26% | 35% | 0.55 |
| embeddings, no floor | 45% | 67% | 73% | 14% | 27% | 36% | 0.56 |
| hyde | 46% | 69% | 75% | 13% | 30% | 37% | 0.57 |
| hyde + statement | 48% | 67% | 76% | 13% | 29% | 38% | 0.58 |

## your technique works for it — n = 168 queries (170 of 177 solved problems have a relative; median relatives per query 8)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 40% | 64% | 73% | 6% | 17% | 24% | 0.53 |
| embeddings | 55% | 78% | 83% | 9% | 20% | 27% | 0.66 |
| embeddings, no floor | 55% | 80% | 84% | 9% | 20% | 28% | 0.67 |
| hyde | 58% | 80% | 88% | 9% | 23% | 29% | 0.70 |
| hyde + statement | 60% | 81% | 88% | 9% | 23% | 29% | 0.71 |

**Label agreement:** of 122 LeetCode-similar pairs, 78 (64%) share a pattern and 62 (51%) share a technique; for 80 (66%) one's technique works for the other.

**Against `embeddings` on the your technique works for it tier (hit@3):**

- `tags`: fixes 9, breaks 32
- `embeddings, no floor`: fixes 3, breaks 0
- `hyde`: fixes 10, breaks 7
- `hyde + statement`: fixes 10, breaks 5

## Misses at k = 3 — hyde + statement, your technique works for it tier (32)

| Query | Pattern / technique | Expected (up to 3) | hyde + statement top 3 (similarity) | Tags top 3 |
| --- | --- | --- | --- | --- |
| stone-game-iii | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | stone-game-ii (0.71), stone-game (0.68), last-stone-weight-ii (0.64) | stone-game-ii, stone-game, n-th-tribonacci-number |
| distinct-subsequences | 2-D dynamic programming / edit distance / LCS | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, edit-distance | decode-ways (0.55), palindromic-substrings (0.53), unique-paths-ii (0.52) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| design-hashset | arrays & hashing / value as index or bucket | contains-duplicate, find-the-duplicate-number, first-missing-positive | design-hashmap (0.65), lru-cache (0.47), time-based-key-value-store (0.4) | design-hashmap, lru-cache, design-twitter |
| merge-strings-alternately | two pointers / in-place partition | concatenation-of-array, construct-uniform-parity-array-i, count-prefix-and-suffix-pairs-i | merge-sorted-array (0.48), reverse-string (0.47), merge-two-sorted-lists (0.51) | find-median-from-data-stream, remove-element, 3sum |
| stone-game | 2-D dynamic programming / interval DP | best-time-to-buy-and-sell-stock-ii, construct-uniform-parity-array-ii, gas-station | stone-game-ii (0.72), stone-game-iii (0.72), last-stone-weight-ii (0.58) | stone-game-ii, stone-game-iii, n-th-tribonacci-number |
| car-fleet | arrays & hashing / sort then scan | best-time-to-buy-and-sell-stock-ii, construct-uniform-parity-array-ii, daily-temperatures | car-pooling (0.56), asteroid-collision (0.48), single-threaded-cpu (0.46) | daily-temperatures, online-stock-span, sort-an-array |
| reconstruct-itinerary | graph traversal / build adjacency and walk | course-schedule-iv, min-cost-to-connect-all-points | network-delay-time (0.57), car-pooling (0.48), course-schedule (0.48) | network-delay-time, sort-an-array, find-median-from-data-stream |
| interleaving-string | 2-D dynamic programming / grid paths | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | palindromic-substrings (0.6), longest-palindromic-substring (0.58), permutation-in-string (0.59) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| longest-happy-string | heap / top-k | best-time-to-buy-and-sell-stock-ii, construct-uniform-parity-array-ii, gas-station | reorganize-string (0.62), ipo (0.46), longest-substring-without-repeating-characters (0.53) | ipo, task-scheduler, reorganize-string |
| letter-combinations-of-a-phone-number | backtracking / subsets and combinations | combination-sum, combination-sum-ii, design-add-and-search-words-data-structure | open-the-lock (0.53), word-search (0.5), permutations (0.5) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| time-based-key-value-store | binary search / on a sorted array | binary-search, contains-duplicate, guess-number-higher-or-lower | design-hashmap (0.49), lru-cache (0.46), design-twitter (0.4) | lru-cache, design-twitter, design-hashmap |
| construct-uniform-parity-array-i | simulation / follow the rules | concatenation-of-array, count-prefix-and-suffix-pairs-i, cyclically-rotating-a-grid | construct-uniform-parity-array-ii (0.63), partition-equal-subset-sum (0.57), merge-sorted-array (0.47) | n-th-tribonacci-number, k-closest-points-to-origin, evaluate-reverse-polish-notation |
| min-stack | stack / stack simulation | asteroid-collision, baseball-game | online-stock-span (0.5), implement-stack-using-queues (0.49), implement-queue-using-stacks (0.44) | online-stock-span, implement-queue-using-stacks, implement-stack-using-queues |
| generate-parentheses | backtracking / constraint search | climbing-stairs, decode-ways, design-add-and-search-words-data-structure | valid-parenthesis-string (0.55), unique-binary-search-trees-ii (0.5), minimum-add-to-make-parentheses-valid (0.55) | unique-binary-search-trees-ii, target-sum, decode-ways |
| construct-uniform-parity-array-ii | greedy / one-pass local optimum | best-time-to-buy-and-sell-stock-ii, find-the-town-judge, gas-station | construct-uniform-parity-array-i (0.55), partition-equal-subset-sum (0.56), rotate-array (?) | n-th-tribonacci-number, k-closest-points-to-origin, evaluate-reverse-polish-notation |
| two-sum | arrays & hashing / hash map of complements | car-fleet | two-sum-ii-input-array-is-sorted (0.66), 3sum (0.61), first-missing-positive (0.55) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| clone-graph | graph traversal / DFS components / flood fill | accounts-merge, design-add-and-search-words-data-structure, evaluate-division | copy-list-with-random-pointer (0.61), redundant-connection (0.47), binary-tree-right-side-view (0.51) | network-delay-time, redundant-connection, evaluate-division |
| copy-list-with-random-pointer | linked list / copy with a map | add-two-numbers, merge-k-sorted-lists, merge-two-sorted-lists | reorder-list (0.55), reverse-linked-list-ii (0.52), linked-list-cycle (0.46) | lru-cache, linked-list-cycle, design-twitter |
| last-stone-weight | heap / top-k | design-circular-queue, design-hashmap, find-the-town-judge | last-stone-weight-ii (0.6), stone-game (0.57), stone-game-iii (0.55) | sort-an-array, find-median-from-data-stream, reconstruct-itinerary |
| merge-sorted-array | two pointers / opposite ends | 3sum, 4sum, car-fleet | remove-duplicates-from-sorted-array (0.56), rotate-array (0.51), sort-colors (0.46) | find-median-from-data-stream, 3sum, 4sum |
| word-break | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, design-add-and-search-words-data-structure | implement-trie-prefix-tree (0.54), count-prefix-and-suffix-pairs-i (0.58), word-search (0.63) | n-th-tribonacci-number, climbing-stairs, decode-ways |
| single-number | bit manipulation / XOR trick | contains-duplicate, longest-consecutive-sequence, partition-equal-subset-sum | find-the-duplicate-number (0.68), remove-duplicates-from-sorted-array (0.6), first-missing-positive (0.57) | counting-bits, number-of-1-bits, subsets-ii |
| valid-sudoku | arrays & hashing / set membership | contains-duplicate, counting-bits, design-hashset | surrounded-regions (0.53), word-search (0.53), number-of-islands (0.49) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| daily-temperatures | stack / monotonic stack | design-hashset, find-the-duplicate-number, first-missing-positive | car-fleet (0.49), capacity-to-ship-packages-within-d-days (0.51), best-time-to-buy-and-sell-stock-ii (0.49) | car-fleet, online-stock-span, binary-tree-postorder-traversal |
| rotting-oranges | graph traversal / BFS shortest steps | open-the-lock | number-of-islands (0.51), island-perimeter (0.51), max-area-of-island (0.5) | island-perimeter, surrounded-regions, pacific-atlantic-water-flow |
| remove-duplicates-from-sorted-array | two pointers / in-place partition | merge-strings-alternately | find-the-duplicate-number (0.63), remove-element (0.58), merge-sorted-array (0.57) | find-median-from-data-stream, remove-element, 3sum |
| evaluate-reverse-polish-notation | stack / expression evaluation | binary-tree-inorder-traversal, binary-tree-level-order-traversal, binary-tree-postorder-traversal | score-of-parentheses (0.48), minimum-add-to-make-parentheses-valid (0.47), baseball-game (0.44) | n-th-tribonacci-number, binary-tree-postorder-traversal, binary-tree-preorder-traversal |
| longest-increasing-path-in-a-matrix | trees / DFS recursion | balanced-binary-tree, binary-tree-inorder-traversal, binary-tree-level-order-traversal | unique-paths-ii (0.62), max-area-of-island (0.57), pacific-atlantic-water-flow (0.57) | course-schedule, course-schedule-iv, course-schedule-ii |
| maximum-product-subarray | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-ii, best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv | integer-break (0.61), maximum-subarray (0.57), product-of-array-except-self (0.59) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| capacity-to-ship-packages-within-d-days | binary search / on the answer space | longest-palindromic-substring, palindromic-substrings, sqrtx | longest-increasing-subsequence (?), last-stone-weight-ii (0.53), best-time-to-buy-and-sell-stock-ii (0.52) | longest-increasing-subsequence, search-a-2d-matrix, binary-search |
| contains-duplicate | arrays & hashing / set membership | car-fleet, longest-consecutive-sequence, partition-equal-subset-sum | top-k-frequent-elements (0.52), majority-element-ii (0.51), sort-colors (0.56) | top-k-frequent-elements, group-anagrams, valid-anagram |
| count-prefix-and-suffix-pairs-i | simulation / follow the rules | concatenation-of-array, construct-uniform-parity-array-i, cyclically-rotating-a-grid | word-break (0.57), longest-substring-without-repeating-characters (0.58), palindromic-substrings (0.54) | subtree-of-another-tree, longest-common-prefix, design-add-and-search-words-data-structure |

