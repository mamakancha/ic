#!/usr/bin/env python3
import os
import sys
import time

import gflags

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import misc  # noqa
import run_system_baseline_experiment  # noqa

FLAGS = gflags.FLAGS


# Duration in seconds for which to execute workload in each round.
gflags.DEFINE_integer(
    "max_block_payload_size", 4 * 1024 * 1024, "The maximum block payload size allow on the subnet in unit of bytes."
)
gflags.DEFINE_float("rps", 1, "Requests per second.")

# Maximum failure rate and median query duration limit to consider
# for rps to choose as rps_max. If failure rate or latency is higher,
# continue running the benchmark, but do not consider this RPS
# for max capacity
gflags.DEFINE_float(
    "allowable_failure_rate", 0.2, "Maximum failure rate at which to consider the iteration successful."
)
gflags.DEFINE_integer(
    "update_allowable_t_median",
    5000,
    "Maximum update median latency in unit of milliseconds at which to consider the iteration successful.",
)
gflags.DEFINE_integer("max_iterations", 10, "Maximum number of iterations needed in this run.")

# Maximum failure rate and median query duration limit for when to
# stop the benchmark.
# Looks like the workload generator timeout is 30s, so we will never
# see anything higher than that on average.
gflags.DEFINE_float("stop_failure_rate", 0.95, "Maximum failure rate before aborting the benchmark.")
gflags.DEFINE_integer(
    "stop_t_median", 600000, "Maximum median latency in unit of milliseconds before aborting the benchmark."
)

if __name__ == "__main__":
    misc.parse_command_line_args()
    experiment_name = os.path.basename(__file__).replace(".py", "")

    exp = run_system_baseline_experiment.BaselineExperiment()
    exp.start_experiment()

    failure_rate = 0.0
    t_median = 0.0
    payload_size = []
    run = True

    payload_size_max = 0
    payload_size_max_in = None

    num_succ_per_iteration = []

    iteration = 0
    datapoints = misc.get_threshold_approaching_datapoints(FLAGS.max_block_payload_size, 8, 4)

    while run:

        curr_payload_size = datapoints[iteration]
        iteration += 1

        payload_size.append(curr_payload_size)
        print(f"🚀 Testing with payload_size: {curr_payload_size}")

        t_start = int(time.time())

        evaluated_summaries = exp.run_experiment(
            {
                "load_total": FLAGS.rps,
                "duration": FLAGS.iter_duration,
                "arguments": ["--payload-size", str(curr_payload_size)],
            }
        )
        failure_rate, t_median_list, _, _, _, _, _, num_succ, _ = evaluated_summaries.convert_tuple()
        t_median = max(t_median_list)

        num_succ_per_iteration.append(num_succ)

        print(
            f"🚀  ... failure rate for payload size {curr_payload_size} was {failure_rate} median latency is {t_median}"
        )

        duration = int(time.time()) - t_start
        allowable_t_median = FLAGS.update_allowable_t_median
        if failure_rate < FLAGS.allowable_failure_rate and t_median < allowable_t_median:
            if num_succ / duration > payload_size_max:
                payload_size_max = num_succ / duration
                payload_size_max_in = curr_payload_size

        run = failure_rate < FLAGS.stop_failure_rate and t_median < FLAGS.stop_t_median and iteration < len(datapoints)

        # Write summary file in each iteration including experiment specific data.
        rtype = "update"
        state = "running" if run else "done"
        exp.write_summary_file(
            "run_large_payload_experiment",
            {
                "rps": FLAGS.rps,
                "payload_size": payload_size,
                "payload_size_max": payload_size_max,
                "payload_size_max_in": payload_size_max_in,
                "num_succ_per_iteration": num_succ_per_iteration,
            },
            payload_size,
            "payload size [bytes]",
            rtype=rtype,
            state=state,
        )

        print(f"🚀  ... maximum capacity so far is {payload_size_max}")

        if iteration >= FLAGS.max_iterations:
            break

    exp.end_experiment()
