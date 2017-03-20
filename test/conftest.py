import pytest
from collections import namedtuple

from nameko.testing.services import replace_dependencies

from src.service import IndexerService, ProductsService


@pytest.fixture
def config(rabbit_config, web_config):
    config = rabbit_config.copy()
    config.update(web_config)
    return config


@pytest.fixture
def create_service_meta(container_factory, config):

    def create(service_cls, *dependencies, **dependency_map):
        """ Create service instance with specified dependencies mocked
        """
        dependency_names = list(dependencies) + list(dependency_map.keys())

        ServiceMeta = namedtuple(
            'ServiceMeta', ['container'] + dependency_names
        )
        container = container_factory(service_cls, config)

        mocked_dependencies = replace_dependencies(
            container, *dependencies, **dependency_map
        )
        if len(dependency_names) == 1:
            mocked_dependencies = (mocked_dependencies, )

        container.start()

        return ServiceMeta(container, *mocked_dependencies, **dependency_map)

    return create


@pytest.fixture
def products_service(create_service_meta):
    return create_service_meta(ProductsService, 'dispatch')


@pytest.fixture
def indexer_service(create_service_meta):
    return create_service_meta(IndexerService)
