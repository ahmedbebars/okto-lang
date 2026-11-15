# Security policy

Safety is one of Okto's goals, so a weakness in its safety features is treated as a serious bug.

## Supported versions

| Version | Supported |
|---|---|
| 0.4.x | Yes |
| below 0.4 | No |

## What counts as a vulnerability

- A program that reads or writes a file, or reads an environment value, outside its `allow` lines.
- A `secret` value that can be printed, written, logged or turned into a text without `reveal`.
- A value inside `sql(...)` that can change the query text.
- Generated JavaScript or Go code that runs something the Okto program did not say.
- A crash of the compiler that can be triggered by a source file in a way that harms the machine.

A mistake in an Okto program's own logic, or a program whose author allows `"*"`, is not a
vulnerability in Okto.

## How to report

Please **do not open a public issue.** Report it privately through GitHub:

1. Open the [Security tab](https://github.com/ahmedbebars/okto-lang/security) of the repository.
2. Choose **Report a vulnerability**.
3. Include the smallest `.ok` program that shows the problem, the command you ran, and the
   versions of Okto, Python, Node and Go.

## What happens next

- You get an answer within 7 days.
- When the problem is confirmed, a fix is prepared in a private advisory, released, and then
  the advisory is published with credit to you, unless you prefer not to be named.
