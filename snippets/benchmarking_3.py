import openshots as osr
from openshots import fields as f

for solution, avg in osr.results([f.solution(int, f.higher_better), f.estimate]):
	...