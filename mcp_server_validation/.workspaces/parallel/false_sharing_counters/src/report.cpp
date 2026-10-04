#include "report.h"

#include <sstream>

std::string format_stats(const Stats& stats, std::size_t count) {
    std::ostringstream out;
    out << "count=" << count << " sum=" << stats.sum << " above=" << stats.above
        << " even=" << stats.even;
    if (count > 0) {
        out << " mean=" << static_cast<double>(stats.sum) / static_cast<double>(count);
    }
    return out.str();
}
