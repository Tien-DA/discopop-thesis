# This file is part of the DiscoPoP software (http://www.discopop.tu-darmstadt.de)
#
# Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
#
# This software may be modified and distributed under the terms of
# the 3-Clause BSD License.  See the LICENSE file in the package base
# directory for details.

from mcp_server.tools import (
    analyze_code_region,
    create_execution_configuration,
    gather_data,
    get_configurations,
    get_data_dependencies,
    get_execution_results,
    get_parallelization_patches,
    get_parallelization_recommendations,
    get_project_summary,
    initialize_discopop_directory,
    manage_patches,
    run_auto_tuning,
    set_compile_script,
)
