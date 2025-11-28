import openshots as osr

def perform_qem(shots: dict[str, int]) -> dict[str, int]:
	...

i: dict[str, int]
for i in osr.results().filter(backend="ibm_aachen").filter(circuit=qc):
	after_qem: dict[str, int] = perform_qem(i)
	# then compare i and after_qem

shots: dict[str, int] = osr.results().filter(circuit=qc).concat()

shots_int: dict[int, int] = osr.results_int().concat()