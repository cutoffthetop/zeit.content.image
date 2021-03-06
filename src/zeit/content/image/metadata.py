import grokcore.component
import lxml.objectify
import zeit.cms.content.dav
import zeit.cms.content.interfaces
import zeit.content.image.interfaces
import zope.component
import zope.interface
import zope.schema


class ImageMetadata(object):

    zope.interface.implements(zeit.content.image.interfaces.IImageMetadata)

    zeit.cms.content.dav.mapProperties(
        zeit.content.image.interfaces.IImageMetadata,
        zeit.content.image.interfaces.IMAGE_NAMESPACE,
        ('alt', 'caption', 'links_to', 'alignment'))
    zeit.cms.content.dav.mapProperties(
        zeit.content.image.interfaces.IImageMetadata,
        'http://namespaces.zeit.de/CMS/document',
        ('title', 'year', 'volume'))

    _copyrights = zeit.cms.content.dav.DAVProperty(
        zeit.content.image.interfaces.IImageMetadata['copyrights'],
        'http://namespaces.zeit.de/CMS/document', 'copyrights',
        use_default=True)

    @property
    def copyrights(self):
        # migration for nofollow (VIV-104)
        result = list(self._copyrights)
        for i, item in enumerate(result):
            if len(item) == 2:
                result[i] = item + (False,)
        return tuple(result)

    @copyrights.setter
    def copyrights(self, value):
        self._copyrights = value

    zeit.cms.content.dav.mapProperties(
        zeit.content.image.interfaces.IImageMetadata,
        'http://namespaces.zeit.de/CMS/meta',
        ('acquire_metadata',))

    def __init__(self, context):
        self.context = context


@zope.interface.implementer(zeit.connector.interfaces.IWebDAVProperties)
@zope.component.adapter(ImageMetadata)
def metadata_webdav_properties(context):
    return zeit.connector.interfaces.IWebDAVProperties(
        context.context)


@grokcore.component.implementer(zeit.content.image.interfaces.IImageMetadata)
@grokcore.component.adapter(zeit.content.image.interfaces.IImage)
def metadata_for_image(image):
    metadata = ImageMetadata(image)
    # Be sure to get the image in the repository
    parent = None
    if image.uniqueId:
        image_in_repository = parent = zeit.cms.interfaces.ICMSContent(
            image.uniqueId, None)
        if image_in_repository is not None:
            parent = image_in_repository.__parent__
    if zeit.content.image.interfaces.IImageGroup.providedBy(parent):
        # The image *is* in an image group.
        if metadata.acquire_metadata is None or metadata.acquire_metadata:
            group_metadata = zeit.content.image.interfaces.IImageMetadata(
                parent)
            if zeit.cms.workingcopy.interfaces.ILocalContent.providedBy(image):
                for name, field in zope.schema.getFieldsInOrder(
                    zeit.content.image.interfaces.IImageMetadata):
                    value = getattr(group_metadata, name, None)
                    setattr(metadata, name, value)
                metadata.acquire_metadata = False
            else:
                # For repository content return the metadata of the group.
                metadata = group_metadata

    return metadata


class XMLReferenceUpdater(zeit.cms.content.xmlsupport.XMLReferenceUpdater):

    target_iface = zeit.content.image.interfaces.IImageMetadata

    def update_with_context(self, entry, context):
        def set_attribute(name, value):
            if value:
                entry.set(name, value)
            else:
                entry.attrib.pop(name, None)

        set_attribute('title', context.title)
        set_attribute('alt', context.alt)
        set_attribute('align', context.alignment)

        # XXX This is really ugly: XMLReference type 'related' uses href for
        # the uniqueId, but type 'image' uses 'src' or 'base-id' instead, and
        # reuses 'href' for the link information. And since XMLReferenceUpdater
        # is called for all types of reference, we need to handle both ways.
        if entry.get('src') or entry.get('base-id'):
            set_attribute('href', context.links_to)

        entry['bu'] = context.caption or None

        for child in entry.iterchildren('copyright'):
            entry.remove(child)

        for text, link, nofollow in context.copyrights:
            node = lxml.objectify.E.copyright(text)
            if link:
                node.set('link', link)
                if nofollow:
                    node.set('rel', 'nofollow')
            entry.append(node)
