# GitHub Pages' real gem stack, with the observed project-site configuration.
# Run inside the pinned official build image from /usr/local/bundle.
# No credentials are required for these public repository metadata requests.
require "github-pages"
ENV.delete("JEKYLL_GITHUB_TOKEN")
ENV.delete("GITHUB_TOKEN")
Jekyll::Commands::Build.process({
  "source" => "/workspace/src",
  "destination" => "/workspace/out",
  "baseurl" => "/3ds_hub",
  "url" => "https://lafiabrew.github.io",
  "repository" => "lafiabrew/3ds_hub"
})
