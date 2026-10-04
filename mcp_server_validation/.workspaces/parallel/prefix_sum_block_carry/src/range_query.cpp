#include "range_query.h"

#include "prefix_sum.h"

std::vector<long long> answer_range_sums(
    const std::vector<long long>& data,
    const std::vector<std::pair<std::size_t, std::size_t>>& queries) {
    const std::vector<long long> prefix = inclusive_scan_parallel(data);

    std::vector<long long> answers(queries.size());
    for (std::size_t q = 0; q < queries.size(); ++q) {
        const std::size_t l = queries[q].first;
        const std::size_t r = queries[q].second;
        answers[q] = prefix[r] - (l == 0 ? 0 : prefix[l - 1]);
    }
    return answers;
}
