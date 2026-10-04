#include "pipeline.h"

void run_signal(Context& ctx);
void run_geo(Context& ctx);
void run_graph(Context& ctx);
void run_fusion(Context& ctx);
void run_filter(Context& ctx);
void run_codec(Context& ctx);
void run_matrix(Context& ctx);
void run_stats(Context& ctx);
void run_plan(Context& ctx);
void run_audit(Context& ctx);
void run_resample(Context& ctx);
void run_quantize(Context& ctx);
void run_transform(Context& ctx);
void run_index(Context& ctx);

void run_all(Context& ctx) {
    run_signal(ctx);
    run_geo(ctx);
    run_graph(ctx);
    run_fusion(ctx);
    run_filter(ctx);
    run_codec(ctx);
    run_matrix(ctx);
    run_stats(ctx);
    run_plan(ctx);
    run_audit(ctx);
    run_resample(ctx);
    run_quantize(ctx);
    run_transform(ctx);
    run_index(ctx);
}
