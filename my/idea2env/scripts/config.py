# Path constants
DATASET_PATH = "../datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json"
DATASET = "princeton-nlp/SWE-bench_Verified"
ASSERTFLIP_DIR = "../assertflip_contract"
RESULTS_DIR = "../results/default_run/results"

# Other constants
max_attempts = 10
model = "openai/gpt-4o-mini"
phase_mode = "pass_then_invert"  # Options: pass_then_invert (default mode), direct_fail_variant (for the ablations)
max_generation_retries = 10 
