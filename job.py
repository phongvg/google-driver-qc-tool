import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from jobs.batch_job import main

if __name__ == "__main__":
    main()
