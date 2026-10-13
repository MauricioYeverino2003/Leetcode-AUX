# Recall evaluation

_Generated 2026-10-13T07:36+00:00 by `uv run python -m app.recall_eval run` over 178 saved solutions (177 problems). Do not edit by hand._

For each solved problem with a statement and at least one relative, retrieval ran over the user's own rows with the query's own row excluded — by topic tags and by embedding similarity, same rows, same k, the production similarity floor (0.35) — and the top k was scored against three label sets. **hit@k**: a relative in the top k. **recall@k**: share of the relatives in the top k. **MRR**: 1 / rank of the first relative.

- **LeetCode similar**: LeetCode's curated Similar Questions, either direction, among solved problems. External; mixes same-technique with same-series.
- **same pattern**: the saved solutions share a coarse pattern (one of 19). Big buckets; a hit says little.
- **same technique**: the saved solutions share a specific technique (one of 72, `app/recall_eval.py`). This is "solved similarly".

## LeetCode similar — n = 86 queries (86 of 177 solved problems have a relative; median relatives per query 1)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 21% | 44% | 49% | 16% | 38% | 42% | 0.32 |
| embeddings | 60% | 85% | 90% | 48% | 77% | 82% | 0.73 |
| embeddings, no floor | 62% | 87% | 92% | 49% | 80% | 85% | 0.74 |

## same pattern — n = 174 queries (174 of 177 solved problems have a relative; median relatives per query 11)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 49% | 80% | 82% | 5% | 15% | 21% | 0.64 |
| embeddings | 63% | 83% | 86% | 6% | 15% | 22% | 0.73 |
| embeddings, no floor | 64% | 84% | 87% | 6% | 15% | 22% | 0.74 |

## same technique — n = 153 queries (153 of 177 solved problems have a relative; median relatives per query 4)

| Method | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tags | 32% | 55% | 58% | 8% | 21% | 29% | 0.43 |
| embeddings | 45% | 65% | 71% | 14% | 26% | 35% | 0.55 |
| embeddings, no floor | 45% | 67% | 73% | 14% | 27% | 36% | 0.56 |

**Label agreement:** of 122 LeetCode-similar pairs, 78 (64%) share a pattern and 62 (51%) share a technique.

## Misses at k = 3 — embeddings, same technique tier (54)

| Query | Pattern / technique | Expected (up to 3) | Embeddings top 3 (similarity) | Tags top 3 |
| --- | --- | --- | --- | --- |
| rotting-oranges | graph traversal / BFS shortest steps | open-the-lock | number-of-islands (0.51), island-perimeter (0.51), pacific-atlantic-water-flow (0.5) | island-perimeter, surrounded-regions, pacific-atlantic-water-flow |
| minimum-operations-to-reduce-x-to-zero | sliding window / variable size with counts | contains-duplicate-ii, longest-repeating-character-replacement, longest-substring-without-repeating-characters | first-missing-positive (0.52), subarray-sum-equals-k (?), find-minimum-in-rotated-sorted-array (0.48) | permutation-in-string, longest-repeating-character-replacement, longest-substring-without-repeating-characters |
| evaluate-division | graph traversal / DFS components / flood fill | accounts-merge, clone-graph, max-area-of-island | — | network-delay-time, redundant-connection, surrounded-regions |
| reverse-nodes-in-k-group | linked list / dummy-head splicing | add-two-numbers, merge-k-sorted-lists, merge-two-sorted-lists | reverse-linked-list (0.54), reorder-list (0.53), reverse-linked-list-ii (0.56) | reorder-list, merge-two-sorted-lists, reverse-linked-list |
| sort-colors | arrays & hashing / counting / frequency map | find-the-town-judge, group-anagrams, top-k-frequent-elements | merge-sorted-array (0.58), 3sum (0.58), remove-duplicates-from-sorted-array (0.56) | find-median-from-data-stream, 3sum, 4sum |
| binary-tree-maximum-path-sum | trees / tree DP (postorder returns) | balanced-binary-tree | diameter-of-binary-tree (0.53), maximum-depth-of-binary-tree (0.55), unique-binary-search-trees-ii (0.51) | diameter-of-binary-tree, binary-tree-postorder-traversal, binary-tree-preorder-traversal |
| cyclically-rotating-a-grid | simulation / follow the rules | concatenation-of-array, construct-uniform-parity-array-i, count-prefix-and-suffix-pairs-i | island-perimeter (0.44), pacific-atlantic-water-flow (0.44), number-of-islands (0.43) | island-perimeter, concatenation-of-array, search-a-2d-matrix |
| valid-sudoku | arrays & hashing / set membership | contains-duplicate, longest-consecutive-sequence, partition-equal-subset-sum | word-search (0.42), surrounded-regions (0.38), open-the-lock (0.37) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| longest-increasing-path-in-a-matrix | trees / DFS recursion | binary-tree-inorder-traversal, binary-tree-level-order-traversal, binary-tree-postorder-traversal | max-area-of-island (0.53), pacific-atlantic-water-flow (0.53), island-perimeter (0.51) | course-schedule, course-schedule-iv, course-schedule-ii |
| majority-element-ii | greedy / one-pass local optimum | best-time-to-buy-and-sell-stock-ii, construct-uniform-parity-array-ii, gas-station | top-k-frequent-elements (?), 3sum (0.55), subarray-sum-equals-k (0.51) | top-k-frequent-elements, task-scheduler, reorganize-string |
| decode-ways | 1-D dynamic programming / Fibonacci-style | climbing-stairs, min-cost-climbing-stairs, n-th-tribonacci-number | palindromic-substrings (0.46), distinct-subsequences (0.45), word-break (?) | n-th-tribonacci-number, jump-game-ii, jump-game |
| accounts-merge | graph traversal / DFS components / flood fill | clone-graph, evaluate-division, max-area-of-island | merge-sorted-array (0.39), find-the-town-judge (0.38), merge-strings-alternately (0.39) | redundant-connection, surrounded-regions, evaluate-division |
| course-schedule-iv | graph traversal / build adjacency and walk | min-cost-to-connect-all-points, reconstruct-itinerary | course-schedule (0.62), course-schedule-ii (0.47), evaluate-division (0.43) | course-schedule-ii, course-schedule, longest-increasing-path-in-a-matrix |
| word-break | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | verifying-an-alien-dictionary (0.5), count-prefix-and-suffix-pairs-i (0.5), implement-trie-prefix-tree (?) | n-th-tribonacci-number, climbing-stairs, decode-ways |
| rotate-array | simulation / follow the rules | concatenation-of-array, construct-uniform-parity-array-i, count-prefix-and-suffix-pairs-i | merge-sorted-array (0.59), remove-duplicates-from-sorted-array (0.53), find-the-duplicate-number (?) | n-th-tribonacci-number, find-median-from-data-stream, remove-element |
| reorganize-string | heap / scheduling with a heap | single-threaded-cpu, task-scheduler | permutation-in-string (0.52), longest-happy-string (0.47), longest-substring-without-repeating-characters (0.46) | task-scheduler, top-k-frequent-elements, ipo |
| letter-combinations-of-a-phone-number | backtracking / subsets and combinations | combination-sum, combination-sum-ii, subsets | open-the-lock (0.44), permutations (0.43), group-anagrams (0.39) | open-the-lock, find-the-town-judge, verifying-an-alien-dictionary |
| time-based-key-value-store | binary search / on a sorted array | binary-search, guess-number-higher-or-lower, search-a-2d-matrix | design-hashmap (0.49), lru-cache (0.44), design-hashset (0.38) | lru-cache, design-twitter, design-hashmap |
| capacity-to-ship-packages-within-d-days | binary search / on the answer space | sqrtx | last-stone-weight-ii (0.45), daily-temperatures (0.4), house-robber (0.39) | longest-increasing-subsequence, search-a-2d-matrix, binary-search |
| clone-graph | graph traversal / DFS components / flood fill | accounts-merge, evaluate-division, max-area-of-island | copy-list-with-random-pointer (0.61), redundant-connection (0.43), network-delay-time (0.42) | network-delay-time, redundant-connection, evaluate-division |
| ipo | heap / two heaps | find-median-from-data-stream | best-time-to-buy-and-sell-stock-ii (0.5), task-scheduler (?), kth-largest-element-in-an-array (?) | task-scheduler, reorganize-string, sort-an-array |
| stone-game | 2-D dynamic programming / interval DP | longest-palindromic-substring, palindromic-substrings | stone-game-iii (0.6), stone-game-ii (0.56), last-stone-weight-ii (0.46) | stone-game-ii, stone-game-iii, n-th-tribonacci-number |
| contains-duplicate | arrays & hashing / set membership | longest-consecutive-sequence, partition-equal-subset-sum, valid-sudoku | find-the-duplicate-number (0.61), contains-duplicate-ii (0.54), first-missing-positive (0.5) | top-k-frequent-elements, group-anagrams, valid-anagram |
| linked-list-cycle | linked list / fast and slow pointers | reorder-list | reverse-linked-list (0.53), remove-nth-node-from-end-of-list (0.48), reverse-linked-list-ii (0.53) | permutation-in-string, lru-cache, find-the-duplicate-number |
| stone-game-iii | 1-D dynamic programming / take-or-skip | best-time-to-buy-and-sell-stock-with-cooldown, combination-sum-iv, house-robber | stone-game (0.65), stone-game-ii (0.58), last-stone-weight-ii (0.5) | stone-game-ii, stone-game, n-th-tribonacci-number |
| find-the-duplicate-number | arrays & hashing / value as index or bucket | design-hashset, first-missing-positive | remove-duplicates-from-sorted-array (0.62), search-in-rotated-sorted-array-ii (0.56), rotate-array (0.52) | two-sum-ii-input-array-is-sorted, linked-list-cycle, find-median-from-data-stream |
| sort-an-array | trees / DFS recursion | binary-tree-inorder-traversal, binary-tree-level-order-traversal, binary-tree-postorder-traversal | merge-sorted-array (0.58), find-minimum-in-rotated-sorted-array (0.57), sort-colors (?) | top-k-frequent-elements, kth-largest-element-in-an-array, k-closest-points-to-origin |
| remove-nth-node-from-end-of-list | linked list / dummy-head splicing | add-two-numbers, merge-k-sorted-lists, merge-two-sorted-lists | reorder-list (0.5), reverse-linked-list-ii (0.55), reverse-linked-list (0.54) | reorder-list, linked-list-cycle, find-median-from-data-stream |
| range-sum-query-2d-immutable | arrays & hashing / prefix sums | product-of-array-except-self, subarray-sum-equals-k | max-area-of-island (0.41), island-perimeter (0.4), number-of-islands (0.39) | island-perimeter, find-median-from-data-stream, serialize-and-deserialize-binary-tree |
| top-k-frequent-elements | arrays & hashing / counting / frequency map | find-the-town-judge, group-anagrams, sort-colors | kth-largest-element-in-an-array (0.55), subarray-sum-equals-k (0.64), majority-element-ii (0.54) | sort-an-array, kth-largest-element-in-an-array, k-closest-points-to-origin |
| reconstruct-itinerary | graph traversal / build adjacency and walk | course-schedule-iv, min-cost-to-connect-all-points | network-delay-time (0.36), course-schedule-ii (0.38), car-pooling (0.38) | network-delay-time, sort-an-array, find-median-from-data-stream |
| subarray-sum-equals-k | arrays & hashing / prefix sums | product-of-array-except-self, range-sum-query-2d-immutable | contains-duplicate-ii (0.56), minimum-operations-to-reduce-x-to-zero (?), partition-equal-subset-sum (0.57) | minimum-operations-to-reduce-x-to-zero, open-the-lock, find-the-town-judge |
| interleaving-string | 2-D dynamic programming / grid paths | minimum-path-sum, unique-paths, unique-paths-ii | permutation-in-string (0.57), palindromic-substrings (0.47), longest-common-subsequence (0.43) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| construct-uniform-parity-array-i | simulation / follow the rules | concatenation-of-array, count-prefix-and-suffix-pairs-i, cyclically-rotating-a-grid | construct-uniform-parity-array-ii (0.63), partition-equal-subset-sum (0.47), merge-sorted-array (0.47) | n-th-tribonacci-number, k-closest-points-to-origin, evaluate-reverse-polish-notation |
| longest-happy-string | heap / top-k | k-closest-points-to-origin, kth-largest-element-in-a-stream, kth-largest-element-in-an-array | reorganize-string (0.47), longest-substring-without-repeating-characters (0.44), valid-parenthesis-string (?) | ipo, task-scheduler, reorganize-string |
| distinct-subsequences | 2-D dynamic programming / edit distance / LCS | edit-distance, longest-common-subsequence | palindromic-substrings (0.51), decode-ways (0.49), permutation-in-string (0.49) | decode-ways, n-th-tribonacci-number, jump-game-ii |
| min-stack | stack / stack simulation | asteroid-collision, baseball-game | implement-stack-using-queues (0.49), online-stock-span (0.46), implement-queue-using-stacks (0.44) | online-stock-span, implement-queue-using-stacks, implement-stack-using-queues |
| find-the-town-judge | arrays & hashing / counting / frequency map | group-anagrams, sort-colors, top-k-frequent-elements | majority-element-ii (0.4), first-missing-positive (0.39), redundant-connection (0.37) | clone-graph, open-the-lock, verifying-an-alien-dictionary |
| construct-uniform-parity-array-ii | greedy / one-pass local optimum | best-time-to-buy-and-sell-stock-ii, gas-station, majority-element-ii | construct-uniform-parity-array-i (0.55), partition-equal-subset-sum (0.5), rotate-array (?) | n-th-tribonacci-number, k-closest-points-to-origin, evaluate-reverse-polish-notation |
| balanced-binary-tree | trees / tree DP (postorder returns) | binary-tree-maximum-path-sum | maximum-depth-of-binary-tree (0.54), validate-binary-search-tree (0.53), count-good-nodes-in-binary-tree (0.48) | binary-tree-postorder-traversal, binary-tree-preorder-traversal, serialize-and-deserialize-binary-tree |
| design-hashset | arrays & hashing / value as index or bucket | find-the-duplicate-number, first-missing-positive | design-hashmap (0.53), lru-cache (0.45), time-based-key-value-store (?) | design-hashmap, lru-cache, design-twitter |
| partition-equal-subset-sum | arrays & hashing / set membership | contains-duplicate, longest-consecutive-sequence, valid-sudoku | target-sum (0.49), subarray-sum-equals-k (0.51), last-stone-weight-ii (?) | target-sum, last-stone-weight-ii, coin-change |
| last-stone-weight | heap / top-k | k-closest-points-to-origin, kth-largest-element-in-a-stream, kth-largest-element-in-an-array | stone-game (0.56), last-stone-weight-ii (0.56), stone-game-iii (0.5) | sort-an-array, find-median-from-data-stream, reconstruct-itinerary |
| open-the-lock | graph traversal / BFS shortest steps | rotting-oranges | minimum-operations-to-reduce-x-to-zero (0.43), letter-combinations-of-a-phone-number (0.4), combination-sum (0.43) | accounts-merge, clone-graph, find-the-town-judge |
| reorder-list | linked list / fast and slow pointers | linked-list-cycle | reverse-linked-list (0.61), reverse-linked-list-ii (0.61), remove-nth-node-from-end-of-list (0.55) | remove-nth-node-from-end-of-list, reverse-nodes-in-k-group, linked-list-cycle |
| best-time-to-buy-and-sell-stock-ii | greedy / one-pass local optimum | construct-uniform-parity-array-ii, gas-station, majority-element-ii | best-time-to-buy-and-sell-stock (0.74), best-time-to-buy-and-sell-stock-with-cooldown (0.64), jump-game-ii (?) | jump-game-ii, jump-game, valid-parenthesis-string |
| last-stone-weight-ii | 1-D dynamic programming / 1-D knapsack | coin-change, coin-change-ii, integer-break | stone-game (0.63), stone-game-ii (0.6), stone-game-iii (0.6) | partition-equal-subset-sum, target-sum, coin-change |
| find-median-from-data-stream | heap / two heaps | ipo | kth-largest-element-in-a-stream (0.45), merge-sorted-array (0.37), majority-element-ii (0.42) | kth-largest-element-in-a-stream, sort-an-array, reconstruct-itinerary |
| merge-strings-alternately | two pointers / in-place partition | remove-duplicates-from-sorted-array | merge-sorted-array (0.44), edit-distance (0.45), permutation-in-string (0.38) | find-median-from-data-stream, remove-element, 3sum |
| sqrtx | binary search / on the answer space | capacity-to-ship-packages-within-d-days | guess-number-higher-or-lower (0.41), perfect-squares (0.38), binary-search (0.38) | n-th-tribonacci-number, longest-increasing-subsequence, search-a-2d-matrix |
| min-cost-to-connect-all-points | graph traversal / build adjacency and walk | course-schedule-iv, reconstruct-itinerary | redundant-connection (0.46), network-delay-time (0.43), max-area-of-island (0.4) | redundant-connection, evaluate-division, find-the-town-judge |
| longest-consecutive-sequence | arrays & hashing / set membership | contains-duplicate, partition-equal-subset-sum, valid-sudoku | first-missing-positive (0.57), subarray-sum-equals-k (0.53), longest-increasing-subsequence (0.55) | accounts-merge, open-the-lock, find-the-town-judge |
| remove-duplicates-from-sorted-array | two pointers / in-place partition | merge-strings-alternately | find-the-duplicate-number (0.6), remove-element (0.58), merge-sorted-array (0.57) | find-median-from-data-stream, remove-element, 3sum |
| daily-temperatures | stack / monotonic stack | online-stock-span | car-fleet (0.39), asteroid-collision (?), first-missing-positive (0.41) | car-fleet, online-stock-span, binary-tree-postorder-traversal |

