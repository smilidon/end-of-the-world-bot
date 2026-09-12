// SPDX-License-Identifier: GPL-3.0-only
import java.io.*;
import net.osmand.binary.*;
import net.osmand.data.*;
import net.osmand.osm.*;
import net.osmand.util.MapUtils;
class CorridorProbe {
 public static void main(String[] a)throws Exception {
  for(String path:a[0].split(java.util.regex.Pattern.quote(File.pathSeparator))){File f=new File(path);var r=new BinaryMapIndexReader(new RandomAccessFile(f,"r"),f);try{
   if(a.length==1){for(var rr:r.getRoutingIndexes())for(var s:rr.getSubregions())System.out.println("COVER\t"+f.getName()+"\t"+s.left+"\t"+s.right+"\t"+s.top+"\t"+s.bottom);continue;}
   var filter=new BinaryMapIndexReader.SearchPoiTypeFilter(){public boolean isEmpty(){return false;}public boolean accept(PoiCategory c,String s){return "fuel".equals(s);}};
   for(int i=1;i<a.length;i+=2){double lat=Double.parseDouble(a[i]),lon=Double.parseDouble(a[i+1]);double dy=0.045,dx=dy/Math.cos(Math.toRadians(lat));
    var req=BinaryMapIndexReader.buildSearchPoiRequest(MapUtils.get31TileNumberX(lon-dx),MapUtils.get31TileNumberX(lon+dx),MapUtils.get31TileNumberY(lat+dy),MapUtils.get31TileNumberY(lat-dy),-1,filter,null);
    int count=0;for(Amenity p:r.searchPoi(req))if("fuel".equals(p.getSubType())&&++count<=100)System.out.println("FUEL\t"+((i-1)/2)+"\t"+f.getName()+"\t"+p.getId()+"\t"+p.getLocation().getLatitude()+"\t"+p.getLocation().getLongitude()+"\t"+p.getName().replaceAll("[\\t\\r\\n]"," ")+"\t"+p.isPrivateAccess());
   }
  }finally{r.close();}}
 }
}
