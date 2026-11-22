"""Parse a response's ``Set-Cookie`` headers, to check the attributes the server sets.

The cookie jar keeps only names and values; flags such as HttpOnly, SameSite,
Secure or Max-Age are only visible in the raw headers.
"""

from http.cookies import Morsel, SimpleCookie

import httpx


def set_cookies(response: httpx.Response) -> dict[str, Morsel[str]]:
    """Every cookie the response sets, by name, with its attributes."""
    cookies: dict[str, Morsel[str]] = {}
    for header in response.headers.get_list("set-cookie"):
        jar: SimpleCookie = SimpleCookie()
        jar.load(header)
        cookies.update(jar)
    return cookies
