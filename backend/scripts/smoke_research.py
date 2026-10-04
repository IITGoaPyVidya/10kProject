"""Live smoke test: run the whole agent team without the HTTP layer.

    python scripts/smoke_research.py TCS.NS [--concall ../samples/concall_july2026_tcs.pdf] [--annual path.pdf]
"""
import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.agents.registry import load_agents  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.services.research_jobs import ResearchStore  # noqa: E402
from app.services.research_pipeline import run_research  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("ticker")
ap.add_argument("--concall")
ap.add_argument("--annual")
ap.add_argument("--youtube")
args = ap.parse_args()

store = ResearchStore(600)
agents = load_agents()
names = [n for n, a in agents.items() if a.config.enabled]
job = store.create(args.ticker, "", "medium", {n: {"title": agents[n].config.title, "stage": agents[n].stage,
                                                    "model": agents[n].config.llm.model} for n in names})
read = lambda p: pathlib.Path(p).read_bytes() if p else None  # noqa: E731
t0 = time.time()
run_research(store, job.id, agent_names=names, concall_pdf=read(args.concall), annual_pdf=read(args.annual),
             youtube_url=args.youtube, settings=get_settings())
snap = store.snapshot(job.id, 0)
print("status:", snap["status"], "| seconds:", round(time.time() - t0), "| error:", snap["error"])
for e in snap["events"]:
    print(f"[{e['ts']:>6}] {e['agent']:<18} {e['level']:<7} {e['message'][:120]}")
f = snap["final"]
if f:
    print("\nFINAL:", f["rating"], f["score"], f["confidence"], "-", f["headline"])
print({n: (a["status"], a.get("rating"), a.get("score")) for n, a in snap["agents"].items()})
