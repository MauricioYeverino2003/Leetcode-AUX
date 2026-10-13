# Recall evaluation

_Generated 2026-10-13T09:20+00:00 by `uv run python -m app.recall_eval run` over 178 saved solutions (177 problems). Do not edit by hand._

For each solved problem with a statement and at least one relative, retrieval ran over the user's own rows with the query's own row excluded — by topic tags and by embedding similarity, same rows, same k, the production similarity floor (0.35) — and the top k was scored against three label sets. **hit@k**: a relative in the top k. **recall@k**: share of the relatives in the top k. **MRR**: 1 / rank of the first relative.

- **LeetCode similar**: LeetCode's curated Similar Questions, either direction, among solved problems. External; mixes same-technique with same-series.
- **same pattern**: the saved solutions share a coarse pattern (one of 19). Big buckets; a hit says little.
- **same technique**: the saved solutions share a specific technique (one of 72, `app/recall_eval.py`). This is "solved similarly".

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

**Label agreement:** of 122 LeetCode-similar pairs, 78 (64%) share a pattern and 62 (51%) share a technique.

**Against `embeddings` on the same technique tier (hit@3):**

- `tags`: fixes 11, breaks 26
- `embeddings, no floor`: fixes 3, breaks 0
- `hyde`: fixes 11, breaks 5
- `hyde + statement`: fixes 7, breaks 3

## Misses at k = 3 — hyde, same technique tier (48)

| Query | Pattern / technique | Expected (up to 3) | hyde top 3 (similarity) | Tags top 3 |
| --- | --- | --- | --- | --- |
| cyclically-rotating-a-grid | simulation / follow the rules | concatenation-of-array, construct-uniform-parity-array-i, count-prefix-and-suffix-pairs-i | number-of-islands (0.44), pacific-atlantic-water-flow (0.43), surrounded-regions (0.43) | island-perimeter, concatenation-of-array, search-a-2d-matrix |
| daily-temperatures | stack / monotonic stack | online-stock-span | car-fleet (0.49), capacity-to-ship-packages-within-d-days (0.51), best-time-to-buy-and-sell-stock-ii (0.49) | car-fleet, online-stock-span, binary-tree-postorder-traversal |
| target-sum | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | partition-equal-subset-sum (0.67), combination-sum-ii (0.59), combination-sum (0.59) | partition-equal-subset-sum, last-stone-weight-ii, unique-binary-search-trees-ii |
| find-the-duplicate-number | arrays & hashing / value as index or bucket | design-hashset, first-missing-positive | linked-list-cycle (0.57), remove-duplicates-from-sorted-array (0.61), search-in-rotated-sorted-array-ii (0.57) | two-sum-ii-input-array-is-sorted, linked-list-cycle, find-median-from-data-stream |
| reorder-list | linked list / fast and slow pointers | linked-list-cycle | remove-nth-node-from-end-of-list (0.59), reverse-linked-list (0.58), merge-two-sorted-lists (0.57) | remove-nth-node-from-end-of-list, reverse-nodes-in-k-group, linked-list-cycle |
| reconstruct-itinerary | graph traversal / build adjacency and walk | course-schedule-iv, min-cost-to-connect-all-points | network-delay-time (0.57), car-pooling (0.48), course-schedule (0.48) | network-delay-time, sort-an-array, find-median-from-data-stream |
| longest-increasing-path-in-a-matrix | trees / DFS recursion | binary-tree-inorder-traversal, binary-tree-level-order-traversal, binary-tree-postorder-traversal | unique-paths-ii (0.62), max-area-of-island (0.57), pacific-atlantic-water-flow (0.57) | course-schedule, course-schedule-iv, course-schedule-ii |
| stone-game | 2-D dynamic programming / interval DP | longest-palindromic-substring, palindromic-substrings | stone-game-ii (0.72), stone-game-iii (0.72), last-stone-weight-ii (0.58) | stone-game-ii, stone-game-iii, n-th-tribonacci-number |
| remove-duplicates-from-sorted-array | two pointers / in-place partition | merge-strings-alternately | find-the-duplicate-number (0.63), remove-element (0.55), merge-sorted-array (0.54) | find-median-from-data-stream, remove-element, 3sum |
| find-the-town-judge | arrays & hashing / counting / frequency map | group-anagrams, sort-colors, top-k-frequent-elements | redundant-connection (0.39), majority-element-ii (0.38), count-good-nodes-in-binary-tree (0.42) | clone-graph, open-the-lock, verifying-an-alien-dictionary |
| distinct-subsequences | 2-D dynamic programming / edit distance / LCS | edit-distance, longest-common-subsequence | decode-ways (0.55), palindromic-substrings (0.53), unique-paths-ii (0.52) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| course-schedule-iv | graph traversal / build adjacency and walk | min-cost-to-connect-all-points, reconstruct-itinerary | course-schedule (0.6), course-schedule-ii (0.59), network-delay-time (0.48) | course-schedule-ii, course-schedule, longest-increasing-path-in-a-matrix |
| ipo | heap / two heaps | find-median-from-data-stream | task-scheduler (0.48), kth-largest-element-in-an-array (0.49), top-k-frequent-elements (0.46) | task-scheduler, reorganize-string, sort-an-array |
| remove-nth-node-from-end-of-list | linked list / dummy-head splicing | add-two-numbers, merge-k-sorted-lists, merge-two-sorted-lists | reorder-list (0.51), reverse-linked-list-ii (0.5), linked-list-cycle (0.45) | reorder-list, linked-list-cycle, find-median-from-data-stream |
| valid-anagram | arrays & hashing / counting / frequency map | find-the-town-judge, group-anagrams, sort-colors | permutation-in-string (0.56), distinct-subsequences (0.54), longest-repeating-character-replacement (0.48) | top-k-frequent-elements, group-anagrams, contains-duplicate |
| letter-combinations-of-a-phone-number | backtracking / subsets and combinations | combination-sum, combination-sum-ii, subsets | open-the-lock (0.53), word-search (0.5), permutations (0.5) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| interleaving-string | 2-D dynamic programming / grid paths | minimum-path-sum, unique-paths, unique-paths-ii | palindromic-substrings (0.6), longest-palindromic-substring (0.58), permutation-in-string (0.59) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| top-k-frequent-elements | arrays & hashing / counting / frequency map | find-the-town-judge, group-anagrams, sort-colors | kth-largest-element-in-an-array (0.57), majority-element-ii (0.54), task-scheduler (?) | sort-an-array, kth-largest-element-in-an-array, k-closest-points-to-origin |
| balanced-binary-tree | trees / tree DP (postorder returns) | binary-tree-maximum-path-sum | maximum-depth-of-binary-tree (0.65), same-tree (0.57), diameter-of-binary-tree (0.56) | binary-tree-postorder-traversal, binary-tree-preorder-traversal, serialize-and-deserialize-binary-tree |
| find-median-from-data-stream | heap / two heaps | ipo | kth-largest-element-in-a-stream (0.5), top-k-frequent-elements (0.53), kth-largest-element-in-an-array (0.45) | kth-largest-element-in-a-stream, sort-an-array, reconstruct-itinerary |
| valid-sudoku | arrays & hashing / set membership | contains-duplicate, longest-consecutive-sequence, partition-equal-subset-sum | surrounded-regions (0.53), word-search (0.53), number-of-islands (0.49) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| design-hashset | arrays & hashing / value as index or bucket | find-the-duplicate-number, first-missing-positive | design-hashmap (0.65), lru-cache (0.47), time-based-key-value-store (0.4) | design-hashmap, lru-cache, design-twitter |
| last-stone-weight | heap / top-k | k-closest-points-to-origin, kth-largest-element-in-a-stream, kth-largest-element-in-an-array | last-stone-weight-ii (0.6), stone-game (0.57), stone-game-iii (0.55) | sort-an-array, find-median-from-data-stream, reconstruct-itinerary |
| word-break | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | implement-trie-prefix-tree (0.54), count-prefix-and-suffix-pairs-i (0.58), word-search (0.63) | n-th-tribonacci-number, climbing-stairs, decode-ways |
| merge-sorted-array | two pointers / opposite ends | 3sum, 4sum, remove-element | remove-duplicates-from-sorted-array (0.56), rotate-array (0.51), sort-colors (0.46) | find-median-from-data-stream, 3sum, 4sum |
| sort-an-array | trees / DFS recursion | binary-tree-inorder-traversal, binary-tree-level-order-traversal, binary-tree-postorder-traversal | kth-largest-element-in-an-array (0.45), sort-colors (0.48), merge-k-sorted-lists (?) | top-k-frequent-elements, kth-largest-element-in-an-array, k-closest-points-to-origin |
| stone-game-iii | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | stone-game-ii (0.71), stone-game (0.68), last-stone-weight-ii (0.64) | stone-game-ii, stone-game, n-th-tribonacci-number |
| longest-happy-string | heap / top-k | k-closest-points-to-origin, kth-largest-element-in-a-stream, kth-largest-element-in-an-array | reorganize-string (0.62), ipo (0.46), longest-substring-without-repeating-characters (0.53) | ipo, task-scheduler, reorganize-string |
| min-stack | stack / stack simulation | asteroid-collision, baseball-game | online-stock-span (0.5), implement-queue-using-stacks (0.44), implement-stack-using-queues (0.43) | online-stock-span, implement-queue-using-stacks, implement-stack-using-queues |
| time-based-key-value-store | binary search / on a sorted array | binary-search, guess-number-higher-or-lower, search-a-2d-matrix | design-hashmap (0.46), lru-cache (0.46), design-twitter (0.4) | lru-cache, design-twitter, design-hashmap |
| construct-uniform-parity-array-ii | greedy / one-pass local optimum | best-time-to-buy-and-sell-stock-ii, gas-station, majority-element-ii | partition-equal-subset-sum (0.56), construct-uniform-parity-array-i (0.47), single-number (0.48) | n-th-tribonacci-number, k-closest-points-to-origin, evaluate-reverse-polish-notation |
| reverse-nodes-in-k-group | linked list / dummy-head splicing | add-two-numbers, merge-k-sorted-lists, merge-two-sorted-lists | reverse-linked-list (0.62), reorder-list (0.6), reverse-linked-list-ii (0.62) | reorder-list, merge-two-sorted-lists, reverse-linked-list |
| rotting-oranges | graph traversal / BFS shortest steps | open-the-lock | max-area-of-island (0.5), pacific-atlantic-water-flow (0.49), surrounded-regions (0.48) | island-perimeter, surrounded-regions, pacific-atlantic-water-flow |
| construct-uniform-parity-array-i | simulation / follow the rules | concatenation-of-array, count-prefix-and-suffix-pairs-i, cyclically-rotating-a-grid | construct-uniform-parity-array-ii (0.55), partition-equal-subset-sum (0.57), two-sum-ii-input-array-is-sorted (0.45) | n-th-tribonacci-number, k-closest-points-to-origin, evaluate-reverse-polish-notation |
| evaluate-division | graph traversal / DFS components / flood fill | accounts-merge, clone-graph, max-area-of-island | redundant-connection (0.51), network-delay-time (0.5), course-schedule (0.44) | network-delay-time, redundant-connection, surrounded-regions |
| count-prefix-and-suffix-pairs-i | simulation / follow the rules | concatenation-of-array, construct-uniform-parity-array-i, cyclically-rotating-a-grid | word-break (0.57), longest-substring-without-repeating-characters (0.58), palindromic-substrings (0.54) | subtree-of-another-tree, longest-common-prefix, design-add-and-search-words-data-structure |
| clone-graph | graph traversal / DFS components / flood fill | accounts-merge, evaluate-division, max-area-of-island | copy-list-with-random-pointer (0.6), redundant-connection (0.47), binary-tree-right-side-view (0.51) | network-delay-time, redundant-connection, evaluate-division |
| subarray-sum-equals-k | arrays & hashing / prefix sums | product-of-array-except-self, range-sum-query-2d-immutable | contains-duplicate-ii (0.6), minimum-operations-to-reduce-x-to-zero (0.54), top-k-frequent-elements (0.48) | minimum-operations-to-reduce-x-to-zero, open-the-lock, find-the-town-judge |
| sqrtx | binary search / on the answer space | capacity-to-ship-packages-within-d-days | search-in-rotated-sorted-array-ii (0.47), search-in-rotated-sorted-array (0.46), number-of-1-bits (0.48) | n-th-tribonacci-number, longest-increasing-subsequence, search-a-2d-matrix |
| contains-duplicate | arrays & hashing / set membership | longest-consecutive-sequence, partition-equal-subset-sum, valid-sudoku | top-k-frequent-elements (0.52), majority-element-ii (0.51), sort-colors (0.56) | top-k-frequent-elements, group-anagrams, valid-anagram |
| merge-strings-alternately | two pointers / in-place partition | remove-duplicates-from-sorted-array | merge-sorted-array (0.48), reverse-string (0.47), merge-two-sorted-lists (0.51) | find-median-from-data-stream, remove-element, 3sum |
| last-stone-weight-ii | 1-D dynamic programming / 1-D knapsack | coin-change, coin-change-ii, integer-break | stone-game (0.62), partition-equal-subset-sum (0.52), target-sum (0.5) | partition-equal-subset-sum, target-sum, coin-change |
| maximum-product-subarray | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | integer-break (0.58), maximum-subarray (0.57), product-of-array-except-self (0.59) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| majority-element-ii | greedy / one-pass local optimum | best-time-to-buy-and-sell-stock-ii, construct-uniform-parity-array-ii, gas-station | top-k-frequent-elements (0.54), sort-colors (0.55), task-scheduler (?) | top-k-frequent-elements, task-scheduler, reorganize-string |
| best-time-to-buy-and-sell-stock-ii | greedy / one-pass local optimum | construct-uniform-parity-array-ii, gas-station, majority-element-ii | best-time-to-buy-and-sell-stock (0.63), best-time-to-buy-and-sell-stock-with-cooldown (0.63), jump-game-ii (0.45) | jump-game-ii, jump-game, valid-parenthesis-string |
| partition-equal-subset-sum | arrays & hashing / set membership | contains-duplicate, longest-consecutive-sequence, valid-sudoku | target-sum (0.56), last-stone-weight-ii (?), coin-change-ii (0.5) | target-sum, last-stone-weight-ii, coin-change |
| accounts-merge | graph traversal / DFS components / flood fill | clone-graph, evaluate-division, max-area-of-island | redundant-connection (0.46), reconstruct-itinerary (0.45), course-schedule (0.45) | redundant-connection, surrounded-regions, evaluate-division |
| capacity-to-ship-packages-within-d-days | binary search / on the answer space | sqrtx | longest-increasing-subsequence (?), last-stone-weight-ii (0.53), best-time-to-buy-and-sell-stock-ii (0.52) | longest-increasing-subsequence, search-a-2d-matrix, binary-search |

