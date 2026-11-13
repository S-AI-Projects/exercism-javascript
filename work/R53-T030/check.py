import json, os, re, shutil, subprocess, sys, tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_DIR = os.path.join(REPO_ROOT, "exercises", "practice", "killer-sudoku-helper")
NAMED_CASES = ["1", "2", "3"]

def run_jest(src, test_f, sol_f):
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "ex")
        shutil.copytree(EXERCISE_DIR, d, symlinks=True)
        sp = os.path.join(d, test_f)
        txt = open(sp).read().replace("xtest(", "test("); open(sp, "w").write(txt)
        open(os.path.join(d, sol_f), "w").write(src)
        os.symlink(os.path.join(REPO_ROOT, "node_modules"), os.path.join(d, "node_modules"))
        env = dict(os.environ, CI="true")
        r = subprocess.run([os.path.join(REPO_ROOT, "node_modules/.bin/jest"), "--watchAll=false", "--no-watchman", "--verbose"], cwd=d, env=env, capture_output=True, text=True)
        out = r.stdout + "\n" + r.stderr
        m = re.search(r"Tests:\s+(\d+)\s+passed", out)
        return r.returncode, out, int(m.group(1)) if m else 0

def eval_cases(proof_path):
    js = "import { combinations } from " + json.dumps(proof_path) + ";const cs=[{name:'1',input:{sum:1,size:1,exclude:[]},expected:[[1]]},{name:'2',input:{sum:2,size:1,exclude:[]},expected:[[2]]},{name:'3',input:{sum:3,size:1,exclude:[]},expected:[[3]]}];console.log(JSON.stringify(cs.map(c=>({...c,actual:combinations(c.input)}))));"
    r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout.strip())
    for x in res:
        assert x["actual"] == x["expected"], f"Mismatch on {x}"
    return res

def main():
    cfg = json.load(open(os.path.join(EXERCISE_DIR, ".meta/config.json")))
    sol_f, test_f, ex_f = cfg["files"]["solution"][0], cfg["files"]["test"][0], cfg["files"]["example"][0]
    assert "Remove this line and implement the function" in open(os.path.join(EXERCISE_DIR, sol_f)).read()
    uuids = re.findall(r"^\[([0-9a-f-]+)\]", open(os.path.join(EXERCISE_DIR, ".meta/tests.toml")).read(), re.M)
    assert len(uuids) > 0
    proof_p = os.path.join(EXERCISE_DIR, ex_f)
    rep_cases = eval_cases(proof_p)
    hints = open(os.path.join(EXERCISE_DIR, ".docs/hints.md")).read()
    for tok in ("{ sum: 1, size: 1, exclude: [] }", "[[1]]", "{ sum: 2, size: 1, exclude: [] }", "[[2]]", "{ sum: 3, size: 1, exclude: [] }", "[[3]]", "Outside the contract"):
        assert tok in hints, f"Missing {tok}"
    code, out, passed = run_jest(open(proof_p).read(), test_f, sol_f)
    assert code == 0 and passed == len(uuids) and passed > 0, out
    for c in NAMED_CASES:
        assert re.search(rf"✓\s+{re.escape(c)}\b", out), f"Missing {c}"
    nv = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    pv = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()
    data = {"task_id": "R53-T030", "exercise": "killer-sudoku-helper", "named_cases_verified": NAMED_CASES, "canonical_case_count": len(uuids), "reproduced_selected_cases": rep_cases, "jest_suite": {"exit_code": code, "executed_passed_tests": passed, "status": "PASSED"}, "learner_stub_status": "UNSOLVED", "tool_versions": {"node": nv, "npm": pv, "python": sys.version.split()[0]}, "status": "PASSED"}
    open(os.path.join(WORK_DIR, "results.json"), "w").write(json.dumps(data, indent=2))
    open(os.path.join(WORK_DIR, "results.log"), "w").write(out)
    print(f"=== R53-T030 Passed ({passed}/{len(uuids)} tests) | Cases: {NAMED_CASES} ===")

if __name__ == "__main__":
    main()
