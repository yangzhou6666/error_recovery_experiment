#! /usr/bin/env python2.7

import math, random, os, sys
from os import listdir, stat

import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['text.usetex'] = True
matplotlib.rcParams['text.latex.preamble'] = [r'\usepackage[cm]{sfmath}']
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = 'cm'
matplotlib.rcParams.update({'errorbar.capsize': 2})
from matplotlib.ticker import ScalarFormatter
import matplotlib.patches as mpatches
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from numpy import histogram

from pykalibera.data import confidence_slice

SRC_FILES_DIR = "src_files"
BOOTSTRAP = 10000
HISTOGRAM_BINS = 75
ERROR_LOCS_HISTOGRAM_BINS = 50
MAX_RECOVERY_TIME = 0.5

class PExec:
    def __init__(self,
                 name,
                 run_num,
                 recovery_time,
                 succeeded,
                 costs,
                 num_lexemes,
                 num_lexemes_skipped):
        self.name = name
        self.run_num = run_num
        self.recovery_time = recovery_time
        self.succeeded = succeeded
        self.costs = costs
        self.num_lexemes = num_lexemes
        self.num_lexemes_skipped = num_lexemes_skipped

class Results:
    def __init__(self,
                 latex_name,
                 pexecs,
                 num_runs):
        self.latex_name = latex_name
        benches = {}
        for p in pexecs:
            if p.name not in benches:
                benches[p.name] = []
            benches[p.name].append(p)
        self.pexecs = list(benches.values())
        self.num_runs = num_runs
        self.bootstrapped_recovery_means = None
        self.bootstrapped_error_locs = None

        sys.stdout.write("%s: recovery_times..." % latex_name)
        sys.stdout.flush()
        self.recovery_time_mean_ci = confidence_slice(self.bootstrap_recovery_means(), "0.99")
        self.recovery_time_median_ci = confidence_slice(self.bootstrap_recovery_medians(), "0.99")
        sys.stdout.write(" failure rates...")
        sys.stdout.flush()
        self.failure_rate_ci = confidence_slice(self.bootstrap_failure_rates(), "0.99")
        sys.stdout.write(" error locations...")
        sys.stdout.flush()
        self.error_locs_ci = confidence_slice(self.bootstrap_error_locs(), "0.99")
        if latex_name != "\\panic":
            sys.stdout.write(" costs...")
            sys.stdout.flush()
            self.costs_ci = confidence_slice(self.bootstrap_costs(), "0.99")
        sys.stdout.write(" input skipped...")
        sys.stdout.flush()
        self.input_skipped_ci = confidence_slice(self.bootstrap_input_skipped(), "0.99")

    def bootstrap_recovery_means(self):
        if self.bootstrapped_recovery_means:
            return self.bootstrapped_recovery_means
        out = []
        for i in range(BOOTSTRAP):
            means = []
            for pexecs in self.pexecs:
                pexec = random.choice(pexecs)
                means.append(pexec.recovery_time)
            out.append(mean(means))
        self.bootstrapped_recovery_means = out
        return out

    def bootstrap_recovery_medians(self):
        out = []
        for i in range(BOOTSTRAP):
            means = []
            for pexecs in self.pexecs:
                pexec = random.choice(pexecs)
                means.append(pexec.recovery_time)
            out.append(median(means))
        return out

    def bootstrap_failure_rates(self):
        out = []
        for i in range(BOOTSTRAP):
            failures = 0
            for pexecs in self.pexecs:
                pexec = random.choice(pexecs)
                if not pexec.succeeded:
                    failures += 1
            out.append((float(failures) / float(len(self.pexecs))) * 100.0)
        return out

    def bootstrap_error_locs(self):
        if self.bootstrapped_error_locs:
            return self.bootstrapped_error_locs
        out = []
        for i in range(BOOTSTRAP):
            error_locs = 0
            for pexecs in self.pexecs:
                pexec = random.choice(pexecs)
                error_locs += len(pexec.costs)
            out.append(error_locs)
        self.bootstrapped_error_locs = out
        return out

    def bootstrap_costs(self):
        out = []
        for i in range(BOOTSTRAP):
            costs = []
            for pexecs in self.pexecs:
                pexec = random.choice(pexecs)
                if pexec.succeeded:
                    costs.extend(pexec.costs)
            if len(costs) > 0:
                out.append(mean(costs))
        return out

    def bootstrap_input_skipped(self):
        out = []
        for i in range(BOOTSTRAP):
            num_lexemes = num_lexemes_skipped = 0
            for pexecs in self.pexecs:
                pexec = random.choice(pexecs)
                num_lexemes += pexec.num_lexemes
                num_lexemes_skipped += pexec.num_lexemes_skipped
            out.append((float(num_lexemes_skipped) / float(num_lexemes)) * 100.0)
        return out

def confidence_ratio_recovery_means(x, y):
    xmeans = x.bootstrap_recovery_means()
    ymeans = y.bootstrap_recovery_means()
    out = []
    for a, b in zip(xmeans, ymeans):
        out.append(float(a / b) * 100.0)
    return confidence_slice(out, "0.99")

def confidence_ratio_error_locs(x, y):
    xmeans = x.bootstrap_error_locs()
    ymeans = y.bootstrap_error_locs()
    out = []
    for a, b in zip(xmeans, ymeans):
        out.append((float(a - b) / float(b)) * 100.0)
    return confidence_slice(out, "0.99")

def mean(l):
    return math.fsum(l) / float(len(l))

def median(l):
    l.sort()
    if len(l) % 2 == 0:
        return mean([l[len(l) // 2 - 1], l[len(l) // 2]])
    else:
        return l[len(l) // 2]

def process(latex_name, p):
    pexecs = []
    num_error_locs = 0
    num_success = 0
    max_run_num = 0
    with open(p) as f:
        for l in f.readlines():
            l = l.strip()
            if len(l) == 0:
                continue
            s = [x.strip() for x in l.split(",")]
            if s[3] == "1":
                succeeded = True
            else:
                assert s[3] == "0"
                succeeded = False
            costs = [int(x) for x in s[4].split(":") if x != ""]
            if latex_name != "\\panic" and succeeded and len(costs) == 0:
                print "Warning: %s (pexec #%s) succeeded without parsing errors" % (s[0], s[1])
                continue
            pexec = PExec(s[0], int(s[1]), float(s[2]), succeeded, costs, int(s[5]), int(s[6]))
            max_run_num = max(max_run_num, pexec.run_num)
            pexecs.append(pexec)

    return Results(latex_name, pexecs, max_run_num + 1)

def corpus_size():
    num_files = 0
    size_bytes = 0
    for l in listdir(SRC_FILES_DIR):
        p = os.path.join(SRC_FILES_DIR, l)
        size_bytes += os.stat(p).st_size
        num_files += 1
    return num_files, size_bytes

def time_histogram(run, p):
    bbins = [[] for _ in range(HISTOGRAM_BINS)]
    bin_width = MAX_RECOVERY_TIME / HISTOGRAM_BINS
    for _ in range(BOOTSTRAP):
        d = [float(random.choice(pexecs).recovery_time) for pexecs in run.pexecs]
        hbins, _ = histogram(d, bins=HISTOGRAM_BINS, range=(0, MAX_RECOVERY_TIME))
        for i, cnt in enumerate(hbins):
            bbins[i].append(cnt)

    bins = []
    errs = []
    for bbin in bbins:
        ci = confidence_slice(bbin, "0.99")
        bins.append(ci.median)
        errs.append(int(ci.error))

    sns.set(style="whitegrid")
    plt.rc('text', usetex=True)
    plt.rc('font', family='sans-serif')
    fig, ax = plt.subplots(figsize=(8, 4))
    plt.bar(range(HISTOGRAM_BINS), bins, yerr=errs, align="center", log=True, color="#777777", \
            error_kw={"ecolor": "black", "elinewidth": 1, "capthick": 0.5, "capsize": 1})
    ax.set_xlabel('Recovery time (s)')
    ax.set_ylabel('Number of files (log$_{10}$)')
    ax.grid(linewidth=0.25)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')
    plt.xlim(xmin=-.2, xmax=HISTOGRAM_BINS)
    locs = []
    labs = []
    for i in range(0, 6):
        locs.append((HISTOGRAM_BINS / 5) * i - 0.5)
        labs.append(i / 10.0)
    plt.xticks(locs, labs)
    yticks = []
    i = len(run.pexecs)
    while i >= 10:
        yticks.append(i)
        i /= 10
    plt.yticks(yticks, [str(x) for x in yticks])
    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    plt.savefig(p, format="pdf")

def calc_max_error_locs(run):
    n = 0
    for pexecs in run.pexecs:
        for pexec in pexecs:
            n = max(n, len(pexec.costs))
    return n

def flat_zip(x, y):
    assert len(x) == len(y)
    out = []
    for z in zip(x, y):
        out.extend(z)
    return out

def error_locs_histogram(run1, run2, p, zoom=None):
    def bins_errs(run, num_bins, max_error_locs):
        bbins = [[] for _ in range(num_bins)]
        bin_width = max_error_locs / num_bins
        for _ in range(BOOTSTRAP):
            d = []
            for pexecs in run.pexecs:
                pexec = random.choice(pexecs)
                if pexec.succeeded:
                    if zoom is None or len(pexec.costs) <= zoom:
                        d.append(len(pexec.costs))
            hbins, _ = histogram(d, bins=num_bins, range=(0, max_error_locs))
            for i, cnt in enumerate(hbins):
                bbins[i].append(cnt)

        bins = []
        errs = []
        for bbin in bbins:
            ci = confidence_slice(bbin, "0.99")
            bins.append(ci.median)
            errs.append(int(ci.error))

        return bins, errs

    if zoom is None:
        max_error_locs = max(calc_max_error_locs(run1), calc_max_error_locs(run2))
    else:
        max_error_locs = zoom
    run1_bins, run1_errs = bins_errs(run1, ERROR_LOCS_HISTOGRAM_BINS, max_error_locs)
    run2_bins, run2_errs = bins_errs(run2, ERROR_LOCS_HISTOGRAM_BINS, max_error_locs)

    sns.set(style="whitegrid")
    plt.rc('text', usetex=True)
    plt.rc('font', family='sans-serif')
    fig, ax = plt.subplots(figsize=(8, 4))
    barlist = plt.bar(range(ERROR_LOCS_HISTOGRAM_BINS * 2), flat_zip(run1_bins, run2_bins), yerr=flat_zip(run1_errs, run2_errs), \
            align="center", log=True, color=["black", "red"], \
            error_kw={"ecolor": "black", "elinewidth": 1, "capthick": 0.5, "capsize": 1})
    for i in range(0, len(barlist), 2):
        barlist[i].set_color("#777777")
        barlist[i + 1].set_color("#BBBBBB")
    mf_patch = mpatches.Patch(color="#777777", label=r"\textrm{MF}")
    mfrev_patch = mpatches.Patch(color="#BBBBBB", label=r"\textrm{MF}$_{\textrm{rev}}$")
    plt.legend(handles=[mf_patch, mfrev_patch])
    ax.set_xlabel('Recovery error locations')
    ax.set_ylabel('Number of files (log$_{10}$)')
    ax.grid(linewidth=0.25)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')
    plt.xlim(xmin=-.7, xmax=ERROR_LOCS_HISTOGRAM_BINS * 2)
    locs = []
    labs = []
    for i in range(0, 8):
        locs.append((ERROR_LOCS_HISTOGRAM_BINS / 7) * i * 2 - 0.5)
        labs.append(int(round((max_error_locs / 7.0) * i)))
    plt.xticks(locs, labs)
    yticks = []
    i = len(run1.pexecs)
    while i >= 10:
        yticks.append(i)
        i /= 10
    plt.yticks(yticks, [str(x) for x in yticks])
    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(formatter)
    plt.savefig(p, format="pdf")

with open("experimentstats.tex", "w") as f:
    # Loading in the CSV files and boostrapping consumes *lots* of memory (gigabytes), so we do it
    # in an order that allows us to keep as few things in memory as we can.
    cpctplus = process("\\cpctplus", "cpctplus.csv")
    mf = process("\\mf", "mf.csv")

    mf_cpctplus_ratio_ci = confidence_ratio_recovery_means(mf, cpctplus)
    f.write(r"\newcommand{\mfcpctplusfailurerateratio}{%.1f\%%{\footnotesize$\pm$%.1f\%%}\xspace}" % \
            (mf_cpctplus_ratio_ci.median, mf_cpctplus_ratio_ci.error))
    f.write("\n")

    # Flush some caches
    mf.bootstrapped_recovery_means = None
    cpctplus.bootstrapped_recovery_means = None

    mfrev = process("\\mfrev", "mf_rev.csv")
    assert cpctplus.num_runs == mf.num_runs == mfrev.num_runs
    mfrev_mf_ratio_ci = confidence_ratio_error_locs(mfrev, mf)
    f.write(r"\newcommand{\mfreverrorlocsratioovermf}{%.1f\%%{\footnotesize$\pm$%.2f\%%}\xspace}" % \
            (mfrev_mf_ratio_ci.median, mfrev_mf_ratio_ci.error))
    f.write("\n")

    panic = process("\\panic", "panic.csv")
    assert cpctplus.num_runs == mf.num_runs == mfrev.num_runs == panic.num_runs

    # Flush all caches
    cpctplus.bootstrapped_recovery_means = None
    cpctplus.bootstrapped_error_locs = None
    mf.bootstrapped_recovery_means = None
    mf.bootstrapped_error_locs = None
    mfrev.bootstrapped_recovery_means = None
    mfrev.bootstrapped_error_locs = None
    panic.bootstrapped_recovery_means = None
    panic.bootstrapped_error_locs = None

    f.write(r"\newcommand{\numruns}{\numprint{%s}\xspace}" % str(cpctplus.num_runs))
    f.write("\n")
    f.write(r"\newcommand{\numbootstrap}{\numprint{%s}\xspace}" % str(BOOTSTRAP))
    f.write("\n")
    num_files, size_bytes = corpus_size()
    f.write(r"\newcommand{\corpussize}{\numprint{%s}\xspace}" % str(num_files))
    f.write("\n")
    f.write(r"\newcommand{\corpussizemb}{\numprint{%s}\xspace}" % str(size_bytes / 1024 / 1024))
    f.write("\n")
    for x in [cpctplus, mf, mfrev, panic]:
        f.write(r"\newcommand{%ssuccessrate}{%.2f\%%{\footnotesize$\pm$%.2f\%%}\xspace}" % \
                (x.latex_name, 100.0 - x.failure_rate_ci.median, x.failure_rate_ci.error))
        f.write("\n")
        f.write(r"\newcommand{%sfailurerate}{%.2f\%%{\footnotesize$\pm$%.2f\%%}\xspace}" % \
                (x.latex_name, x.failure_rate_ci.median, x.failure_rate_ci.error))
        f.write("\n")
        f.write(r"\newcommand{%smeantime}{%.4fs{\footnotesize$\pm$%.4fs}\xspace}" % \
                (x.latex_name, x.recovery_time_mean_ci.median, x.recovery_time_mean_ci.error))
        f.write("\n")
        f.write(r"\newcommand{%smediantime}{%.4fs{\footnotesize$\pm$%.4fs}\xspace}" % \
                (x.latex_name, x.recovery_time_median_ci.median, x.recovery_time_median_ci.error))
        f.write("\n")
        f.write(r"\newcommand{%serrorlocs}{\numprint{%s}{\footnotesize$\pm$\numprint{%s}}\xspace}" % \
                (x.latex_name, x.error_locs_ci.median, x.error_locs_ci.error))
        f.write("\n")

with open("table.tex", "w") as f:
    for x in [panic, cpctplus, mf, mfrev]:
        if x.latex_name == "\\panic":
            costs_median = "-"
            costs_ci = ""
        else:
            costs_median = "%.2f" % x.costs_ci.median
            costs_ci = "{\scriptsize$\pm$%.3f}" % x.costs_ci.error
            print x.costs_ci
        f.write("%s & %.6f & %.6f & %s & %.2f & %.2f & \\numprint{%d} \\\\[-4pt]\n" % \
                (x.latex_name, \
                 x.recovery_time_mean_ci.median, \
                 x.recovery_time_median_ci.median, \
                 costs_median, \
                 x.failure_rate_ci.median, \
                 x.input_skipped_ci.median, \
                 x.error_locs_ci.median))
        f.write("%s & {\scriptsize$\pm$%.7f} & {\scriptsize$\pm$%.7f} & %s & {\scriptsize$\pm$%.3f} & {\scriptsize$\pm$%.3f} & {\scriptsize$\pm$%s}\\\\\n" % \
                (" " * len(x.latex_name), \
                 x.recovery_time_mean_ci.error, \
                 x.recovery_time_median_ci.error, \
                 costs_ci, \
                 x.failure_rate_ci.error, \
                 x.input_skipped_ci.error, \
                 int(x.error_locs_ci.error)))
        if x.latex_name == "\\panic":
            f.write("\midrule\n")

sys.stdout.write("Time histograms...")
sys.stdout.flush()
time_histogram(cpctplus, "cpctplus_histogram.pdf")
sys.stdout.write(" cpctplus")
sys.stdout.flush()
time_histogram(mf, "mf_histogram.pdf")
sys.stdout.write(" mf")
sys.stdout.flush()
time_histogram(mfrev, "mfrev_histogram.pdf")
sys.stdout.write(" mfrev")
sys.stdout.flush()
time_histogram(panic, "panic_histogram.pdf")
sys.stdout.write(" panic")
sys.stdout.flush()
print
sys.stdout.write("Error locations histogram...")
sys.stdout.flush()
error_locs_histogram(mf, mfrev, "mf_mfrev_error_locs_histogram_full.pdf")
sys.stdout.write(" mf/mfrev full")
sys.stdout.flush()
error_locs_histogram(mf, mfrev, "mf_mfrev_error_locs_histogram_zoomed.pdf", zoom=50)
sys.stdout.write(" mf/mfrev zoomed")
sys.stdout.flush()
error_locs_histogram(mf, panic, "mf_panic_error_locs_histogram_full.pdf")
sys.stdout.write(" mf/panic full")
sys.stdout.flush()
print
