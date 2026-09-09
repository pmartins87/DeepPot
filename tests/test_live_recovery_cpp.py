from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_cpp_recovery_matches_log_pf2_and_edge_cases(tmp_path: Path) -> None:
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ unavailable")

    repo = Path(__file__).resolve().parents[1]
    main_cpp = tmp_path / "main.cpp"
    main_cpp.write_text(
        r'''#include <array>
#include <iostream>
#include <vector>
#include "deeppot_live_recovery.h"

using deeppot_runtime::Card;
using deeppot_runtime::LiveScrapeSnapshot;
using deeppot_runtime::PublicStateCandidate;

LiveScrapeSnapshot S(int dealer, int user, unsigned dealt, unsigned playing, unsigned folded, int n) {
  LiveScrapeSnapshot s;
  s.nchairs = 8;
  s.dealerchair = dealer;
  s.userchair = user;
  s.playersdealtbits = dealt;
  s.playersplayingbits = playing;
  s.foldbits2 = folded;
  s.nplayersdealt = n;
  return s;
}

bool Check(const LiveScrapeSnapshot& s, int n, int actor, unsigned mask, int dense, int code) {
  std::vector<LiveScrapeSnapshot> history;
  std::vector<PublicStateCandidate> c = deeppot_runtime::RecoverPublicStateCandidates(s, history);
  if (c.empty()) return false;
  return c[0].num_players == n && c[0].actor_index == actor &&
         c[0].prior_stay_mask == mask && c[0].scenario_dense_id == dense &&
         c[0].global_scenario_code == code;
}

int main() {
  if (!Check(S(5,2,247,117,128,7), 7,4,5,20,135)) return 10;
  if (!Check(S(3,2,255,77,176,8), 8,6,20,83,324)) return 11;
  if (!Check(S(5,2,255,60,193,8), 8,4,0,15,256)) return 12;
  if (!Check(S(2,2,255,13,240,8), 8,7,33,159,400)) return 13;
  if (!Check(S(4,2,255,28,224,8), 8,5,0,31,272)) return 14;
  if (!Check(S(5,2,255,61,192,8), 8,4,4,19,260)) return 15;

  // Missing current BTN -> same-hand BTN history.
  LiveScrapeSnapshot current = S(-1,2,255,28,224,8);
  std::vector<LiveScrapeSnapshot> history;
  history.push_back(S(4,2,255,255,0,8));
  std::vector<PublicStateCandidate> recovered =
      deeppot_runtime::RecoverPublicStateCandidates(current, history);
  if (recovered.empty() || recovered[0].global_scenario_code != 272) return 20;

  // Contradictory playing+folded prior actor must branch instead of MISS.
  LiveScrapeSnapshot contradiction = S(4,2,255,28 | (1u << 5),224 | (1u << 5),8);
  recovered = deeppot_runtime::RecoverPublicStateCandidates(contradiction, {});
  if (recovered.empty()) return 30;
  const int min_cost = recovered[0].cost;
  bool saw_fold = false;
  bool saw_stay = false;
  for (const PublicStateCandidate& c : recovered) {
    if (c.cost != min_cost) continue;
    if (c.prior_stay_mask == 0) saw_fold = true;
    if (c.prior_stay_mask == 1) saw_stay = true;
  }
  if (!saw_fold || !saw_stay) return 31;

  // Tc7s on 7d6h4d is top pair; Ts9s on Th3sAd is only second pair.
  std::array<Card,3> flop_tp = {{{7,1},{6,2},{4,1}}};
  std::array<Card,2> hole_tp = {{{10,0},{7,3}}};
  if (!deeppot_runtime::IsTopPairOrBetter(flop_tp, hole_tp)) return 40;
  std::array<Card,3> flop_second = {{{10,2},{3,3},{14,1}}};
  std::array<Card,2> hole_second = {{{10,3},{9,3}}};
  if (deeppot_runtime::IsTopPairOrBetter(flop_second, hole_second)) return 41;

  std::cout << "OK\n";
  return 0;
}
''',
        encoding="utf-8",
    )
    exe = tmp_path / "live_recovery_test"
    subprocess.run(
        [
            compiler,
            "-std=c++11",
            "-O2",
            "-I",
            str(repo / "runtime"),
            str(repo / "runtime" / "deeppot_runtime_core.cpp"),
            str(repo / "runtime" / "deeppot_live_recovery.cpp"),
            str(main_cpp),
            "-o",
            str(exe),
        ],
        check=True,
    )
    completed = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert completed.stdout.strip() == "OK"
