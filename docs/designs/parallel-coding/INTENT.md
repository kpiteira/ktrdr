I would like to improve my overall setup for working with you (Claude Code),
  including:

- leverage the amazing capability of the status lines of the Claude Code CLI. Here is what it
  looks like right now (attached). As you can see, it only takes a portion of my terminal (which
  itself if half of my screen horizontally (see 2nd attachment to see my setup with Zellij) not
  sure why. But the thing is that I would like to have more clarity about what we're working on
  in a given terminal. This could be achieved by the current or last thing done. e.g if I started
  a `kmilestone` command, I'd like to see the project and milestone name in the status
  `project/milestone`. If i started a `ktask` it would be awesome to have it there too like
  `project/milestone/task` kind of thing. If I just merged a PR, I'd like to replace that by
  `merged <project/milestone>, next: <next milestone | done!>`. For clarity, for the one we just
  completed in @docs/designs/indicator-fuzzy-cleanup/ the project would be
  `indicator-fuzzy-cleanup`, the milestone we just merged was `M5_documentation` and we're done.
- I'm starting to think that this model of having everything visible is not going to be
  enough soon. I see a lot of people more advanced than me in Claude Code usage, start to use an
  agent manager and switch from one terminal to another (I think most are using something built
  on tmux). I find myself trending toward that as I am able to have longer running autonomous
  work with `kmilestone` so I could have more in parallel work going on, all the while I work on 1 or 2 specs. I'd love some research on that!
- As a corrolary to that, my current system of Sandboxes is really cool to be able to do e2e tests, but it has a few flaws:
   1- While designed initially for gittree, my model doesn't really allow that because each milestone is typically merged to main, so if I start a tree branch in a folder with a sandbox, as soon as the milestone is done it cannot merge to main. So what I do today is long lived clones of the repo with their own sandbox (like the current one we're in)
   2- Sandboxes are a real memory hog. Now in fairness, they have the full environment but at the same time that's kind of the point. and right now the only thing I see we could lighten is having 1 worker of each (training and backtesting) instead of 2. Not sure about the real gain :/. e.g I have 2 sandboxes + the local prod deployed, together they represent 7.5GB... while doing pretty much nothing. All this to say that I could maybe instantiate 2 more but not much more.
   3- Bringing up a sandbox is reasonnable but I'm not sure I want to do that every time I start a new milestone. getting it up is OK, but the build is painful,  it redownloads everything (for some reason there is no cache) and the builds an up, it take time and bandwidth
   4- I'm sure there's more, but you see why the sandboxes are not super scalable, but they provide huge value!
- finally, similar to when I start a new sandbox and it is able to create a new gittree, it would be cool to be able to create a new tree branch without a sandbox for spec work, and have that tracked somehow somewhere. Right now I either do my spec work in ../ktrdr2-spec-work or in one of my sandboxes. I'd like that to be a bit better organized!

I know that's a lot, with a lot of unclarity, brainstorming, research and conversation to do. I am trying to maybe slow down a bit right now to accelerate after, and set up a great system!
I also wanted to ask YOU the question: how can I make the environment easier for YOU?!
