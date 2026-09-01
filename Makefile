.PHONY: bootstrap run test verify verify-package sync-docs wheel package tree

bootstrap:
	bash scripts/bootstrap.sh

run:
	bash scripts/run.sh

test:
	bash scripts/test.sh

verify:
	bash scripts/verify.sh

verify-package:
	bash scripts/verify-package.sh

sync-docs:
	bash scripts/sync-docs.sh

wheel:
	bash scripts/wheel.sh

package:
	bash scripts/package.sh

tree:
	find . -maxdepth 5 -type f | sort
