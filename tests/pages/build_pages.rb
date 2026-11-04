# Official github-pages stack with observed project configuration and a reduced
# source surface. Local anonymous builds need no credentials; CI may supply its
# ephemeral contents-read token for public metadata quota, never a stored secret.
require "json"
require "github-pages"
token = ENV["JEKYLL_GITHUB_TOKEN"]
ENV.delete("JEKYLL_GITHUB_TOKEN") if token.nil? || token.empty?
ENV.delete("GITHUB_TOKEN")
manifest = JSON.parse(File.read("/workspace/src/site/docs-manifest.json"))
Jekyll::Commands::Build.process({
  "source" => "/workspace/src",
  "destination" => "/workspace/out",
  "baseurl" => manifest.fetch("base_path").chomp("/"),
  "url" => "https://lafiabrew.github.io",
  "repository" => "lafiabrew/3ds_hub",
  "exclude" => manifest.fetch("source_only") + ["tests", "tools", "templates", "releasekit", "site",
                                                "pc_companion", "serve_3ds.py", "Makefile", "_site", "_docs", "_publication"]
})
