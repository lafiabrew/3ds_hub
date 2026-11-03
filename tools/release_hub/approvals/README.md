# Independent approval data registry — empty initially

No application is approved by this directory's existence. Records may be added
only from the app coordinator's exact-source qualification and independently
reviewed central-hub integration; the release-kit author creates none.
Filename is SHA256 of exact record bytes plus `.json`.

The executable workflow and kit remain pinned together to K0. A separate,
immutable `approval_ref` R1 supplies **JSON data only**, verified as reachable on
public hub main. R1 is never checked out or executed. This avoids changing the
app's source A0 to repin its caller after approving A0. See
`docs/RELEASING.md` for the precise schema, transaction and trust boundary.
