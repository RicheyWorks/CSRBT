# ADR-217 — A quoted phrase with a space in it cost a commit, and the script said it had pushed

**ADR-215's commit subject quoted the phrase `"everything is green"`. PowerShell re-quotes every argument on its way to a native `.exe`, the quote characters do not survive, and git re-split the argument on the spaces that had been inside them — receiving `is` and `green beside a reading of 6 / 7, …` as PATHSPECS. Two errors. Nothing committed. Then `git push` answered "Everything up-to-date" — true, there was nothing new — and the script printed `ADR215 pushed.` The delivery layer told the one person relying on it that his work was on the remote when it was on no branch at all.**

## 1. It had been working by accident since ADR-150

Six manifests before this one carry straight double quotes in their bodies, and
every one of them pushed cleanly:

    adr150   "3e"   ""
    adr205   "buttons"
    adr208   "_in"

**None of those quoted strings contains a space.** PowerShell's re-quoting loses
the quote characters; git then splits the argument on whitespace, and an argument
with no whitespace inside its quotes comes out the far side unharmed. Seven
slices' worth of evidence that the escaping worked, and all of it was evidence
about a case that cannot fail.

### The first answer was wrong too

The fix shipped an hour after the failure turned the straight quote into a
typographic one — `“everything is green”` — on the theory that the straight quote
was the problem. The regenerated script failed **in the same place**:

    error: pathspec 'everything' did not match any file(s) known to git
    error: pathspec 'is' did not match any file(s) known to git

A typographic double quote delimits a PowerShell string as surely as a straight
one, and *unlike* the straight one it cannot be backtick-escaped. Same failure,
one character further along.

So the rule is the **mechanism** and the mechanism is about spaces: `ps_quote`
escapes a straight quote as it always did, turns a typographic one into a single
quote because it cannot be escaped at all, and `--check` refuses a straight-quoted
phrase **containing a space**. A quoted string with no space in it is fine, and
sixty slices of evidence say so.

## 2. And the script said it worked

    $ErrorActionPreference = "Stop"

governs PowerShell **cmdlets**. It says nothing about `git.exe` returning 1. So
the failed commit ran straight on to the push, and the push to `Write-Host`.

This is ADR-203's shape — a message asserting what was not observed — and
ADR-212's, exactly: *"bench.csv downloaded"* over a download that could not
start. Those cost a reader a file they thought they had. **This one is the layer
those records travel on.** Every push script in this kit ended by printing that
the slice was pushed, and none of them had ever checked.

Every script now:

1. reads `$LASTEXITCODE` after `git commit` and stops if it is non-zero;
2. checks the **post-condition** — this slice's own manifest must be in `HEAD` —
   before pushing anything. An exit code is what the tool says about itself; this
   is what the repository says about it, and it is true if and only if the commit
   happened;
3. reads `$LASTEXITCODE` after `git push`, because a commit that is local and a
   remote that does not have it are different states and only one of them is
   "pushed".

## 3. All 69 scripts are regenerated

The rule this kit has held since ADR-184 is that the push script is **generated,
never edited** — `deliver.py --check` compares each script against what its
manifest generates, and a hand edit is a failure. A change to the generator
therefore means every script, including sixty-eight that have already run and
will never run again. That is the cost of the rule and it is the right cost: the
alternative is a generator that produces one thing and a directory that contains
another.

## 4. What checks it

`verify_delivery` 43 → 50: the exit code is read before anything is pushed; the
push's exit code before the word; the post-condition is present and before the
push; a straight quote is **curled rather than escaped**; and no manifest in the
kit still quotes a phrase with a space in it. The pre-ADR-184 check that a
manifest without `"once"` gets no guard now asks about the *once-guard* rather
than about the words `ls-tree HEAD`, because every script asks git that question
now for a different reason.

## 5. What this run has now found three times

ADR-212: a handler that knew a download could fail silently, declined to mark the
outbox for that reason, and then said the file had downloaded.
ADR-216: a tile that needed a reason, was given one, and asserted a ratchet
nobody had built.
ADR-217: a script that printed the one word its reader was waiting for, having
checked nothing.

**A sentence is not a measurement.** The kit has audits for what a page says to a
reader and had nothing for what its own tooling says to the person running it.
